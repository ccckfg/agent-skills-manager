from __future__ import annotations

from pathlib import Path

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.domain.models import (
    AgentDefinition,
    PromptAction,
    PromptInventory,
    PromptPlan,
    PromptTarget,
)
from agent_skills_manager.infrastructure.prompt_store import PromptStore
from agent_skills_manager.services.detector import AgentDetector


def prompts_file(central_skills_path: Path) -> Path:
    """The canonical prompt lives next to the central skills store, not inside it."""
    return central_skills_path.parent / "prompts" / "user.md"


def capture_prompt(
    store: PromptStore,
    source: Path,
    origin: Path,
    backup_root: Path,
) -> Path | None:
    """Seed the canonical prompt from one host's instruction file.

    An existing canonical file is moved into ``backup_root`` first. Raises when
    the origin file is missing so callers can surface a clear error.
    """
    content = store.read(origin)
    if content is None:
        raise FileNotFoundError(f"No prompt file to capture: {origin}")
    backup = store.backup_file(source, backup_root)
    store.write(source, store.canonical(content))
    return backup


class PromptInventoryService:
    def __init__(self, registry: AgentRegistry, store: PromptStore | None = None) -> None:
        self.registry = registry
        self.store = store or PromptStore()
        self.detector = AgentDetector(registry)

    def scan(self, source: Path) -> PromptInventory:
        """Resolve every host's prompt file and compare it with the canonical content.

        Prompt files are small, so unlike the Skills inventory this always compares
        content; there is no cheap "presence only" mode to get wrong.
        """
        content = self.store.read(source)
        targets = [
            self._target(definition, content)
            for definition in self.registry.all()
            if definition.prompts_paths
        ]
        return PromptInventory(source=source, source_present=content is not None, targets=targets)

    def _target(self, definition: AgentDefinition, content: str | None) -> PromptTarget:
        path = self.detector.prompt_path(definition)
        present = path.is_file()
        matches = None
        if content is not None:
            # With a canonical source, an absent file simply does not match yet.
            matches = False
            if present:
                rendered = self.store.render(content, definition.prompt_style)
                matches = self.store.matches(path, rendered)
        return PromptTarget(
            agent_id=definition.id,
            display_name=definition.display_name,
            path=path,
            style=definition.prompt_style,
            present=present,
            matches=matches,
        )


class PromptSyncService:
    def __init__(self, store: PromptStore | None = None) -> None:
        self.store = store or PromptStore()

    def plan(self, inventory: PromptInventory, selected: set[str] | None = None) -> PromptPlan:
        """Build a pure write plan; never touch the filesystem."""
        plan = PromptPlan()
        if not inventory.source_present:
            plan.warnings.append(
                f"No canonical prompt file at {inventory.source}. "
                "Seed it with: agent-skills-manager prompts capture --from <agent>"
            )
            return plan
        claimed: dict[Path, str] = {}
        for target in inventory.targets:
            if selected and target.agent_id not in selected:
                continue
            if target.matches:
                continue
            resolved = target.path.resolve()
            if resolved in claimed:
                plan.warnings.append(
                    f"{target.display_name} and {claimed[resolved]} share one prompt "
                    "file; one write covers both."
                )
                continue
            claimed[resolved] = target.display_name
            plan.actions.append(
                PromptAction(
                    agent_id=target.agent_id,
                    destination=target.path,
                    source=inventory.source,
                    style=target.style,
                    replace=target.present,
                )
            )
        return plan

    def execute(self, plan: PromptPlan, allowed: set[Path], backup_root: Path) -> list[Path]:
        """Write the planned prompt files, backing up anything they replace."""
        allowed_paths = {path.resolve() for path in allowed}
        backups = []
        for action in plan.actions:
            if not action.source.is_file():
                raise FileNotFoundError(f"Canonical prompt file disappeared: {action.source}")
            if action.destination.resolve() not in allowed_paths:
                raise ValueError(
                    f"Refusing destination outside known prompt targets: {action.destination}"
                )
            content = self.store.render(self.store.read(action.source) or "", action.style)
            backup = self.store.backup_file(action.destination, backup_root / action.agent_id)
            try:
                self.store.write(action.destination, content)
            except Exception:
                if backup and not action.destination.exists():
                    backup.replace(action.destination)
                raise
            if backup:
                backups.append(backup)
        return backups
