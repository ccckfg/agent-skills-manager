from __future__ import annotations

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import (
    AgentInventory,
    InventorySnapshot,
    ItemStatus,
    McpEntry,
    SkillEntry,
)
from agent_skills_manager.infrastructure.mcp_reader import McpReader
from agent_skills_manager.infrastructure.skill_store import SkillStore
from agent_skills_manager.services.detector import AgentDetector


class InventoryService:
    def __init__(
        self,
        settings: Settings,
        registry: AgentRegistry | None = None,
        store: SkillStore | None = None,
        reader: McpReader | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry or AgentRegistry.load_default()
        self.store, self.reader = store or SkillStore(), reader or McpReader()
        self.detector = AgentDetector(self.registry)

    def scan(self, verify_contents: bool = True) -> InventorySnapshot:
        """Inspect configured agents.

        ``verify_contents=False`` is intended for the interactive browser: it
        reports presence and link health without hashing every copied file.
        Synchronization and CLI status keep the full verification default.
        """
        central = self.settings.central_skills_path
        canonical = self.store.children(central)
        canonical_digests: dict[str, str] = {}
        inventories = [
            self._agent(definition, canonical, verify_contents, canonical_digests)
            for definition in self.registry.all()
        ]
        return InventorySnapshot(agents=inventories, central_skills_path=central)

    def _agent(self, definition, canonical, verify_contents, canonical_digests) -> AgentInventory:
        skills_path, mcp_path = self.detector.paths_for(definition)
        local = self.store.children(skills_path)
        entries = [
            self._skill(
                name,
                source,
                local.pop(name, None),
                verify_contents,
                canonical_digests,
            )
            for name, source in canonical.items()
        ]
        entries.extend(
            SkillEntry(
                name=name,
                path=path,
                status=ItemStatus.UNMANAGED,
                is_link=self.store.is_link(path),
            )
            for name, path in local.items()
        )
        mcps = [
            McpEntry(name=name, config_path=mcp_path)
            for name in self.reader.server_names(mcp_path, definition.mcp_format)
        ]
        return AgentInventory(
            definition=definition,
            installed=self.detector.installed(definition),
            skills_path=skills_path,
            mcp_path=mcp_path,
            preference=self.settings.preference_for(definition.id),
            skills=entries,
            mcps=mcps,
        )

    def _skill(self, name, source, target, verify_contents, canonical_digests) -> SkillEntry:
        if target is None:
            return SkillEntry(name=name, path=source, status=ItemStatus.MISSING)
        is_link = self.store.is_link(target)
        if is_link and not target.exists():
            return SkillEntry(name=name, path=target, status=ItemStatus.BROKEN, is_link=True)
        if is_link:
            status = (
                ItemStatus.READY
                if not verify_contents or self.store.points_to(target, source)
                else ItemStatus.DIFFERENT
            )
        elif not verify_contents:
            status = ItemStatus.READY
        else:
            if name not in canonical_digests:
                canonical_digests[name] = self.store.digest(source)
            source_digest = canonical_digests[name]
            status = (
                ItemStatus.READY
                if source_digest == self.store.digest(target)
                else ItemStatus.DIFFERENT
            )
        return SkillEntry(name=name, path=target, status=status, is_link=is_link)


def load_inventory(
    settings_path: str | None = None,
    verify_contents: bool = True,
) -> InventorySnapshot:
    """Load an inventory with the default on-disk configuration."""
    return InventoryService(Settings.load(settings_path)).scan(verify_contents=verify_contents)
