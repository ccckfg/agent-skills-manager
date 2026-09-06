"""Plan and apply user-level instruction file synchronization.

Every supported host loads one user-level prompt file (AGENTS.md, CLAUDE.md,
GEMINI.md, ...) into every session. The canonical content lives next to the
central Skills store so both trees share one backup area.
"""

from dataclasses import replace
from pathlib import Path
from typing import Iterable, List, Optional, Set

from .models import Action, AgentProfile, Plan, PromptTarget
from .store import backup

CURSOR_STYLE = "cursor"


def prompts_file(central: Path) -> Path:
    return central.parent / "prompts" / "user.md"


def normalize(text: str) -> str:
    """Ignore CRLF and trailing-newline differences between prompt files."""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def render(content: str, style: str) -> str:
    body = normalize(content)
    if style == CURSOR_STYLE:
        return "---\ndescription: User coding instructions\nalwaysApply: true\n---\n\n{}\n".format(
            body
        )
    return body + "\n"


def load_targets(profiles: Iterable[AgentProfile]) -> List[PromptTarget]:
    return [
        PromptTarget(
            id=profile.id,
            display_name=profile.display_name,
            path=profile.prompt_path,
            style=profile.prompt_style,
            present=profile.prompt_path.is_file(),
        )
        for profile in profiles
        if profile.prompt_path is not None
    ]


def _content_of(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def scan_prompts(source: Path, targets: List[PromptTarget]) -> List[PromptTarget]:
    """Compare every target with the canonical content; prompt files are small."""
    content = _content_of(source)
    scanned = []
    for target in targets:
        matches = None
        if content is not None:
            current = _content_of(target.path)
            # With a canonical source, an absent file simply does not match yet.
            matches = False
            if current is not None:
                matches = normalize(current) == normalize(render(content, target.style))
        scanned.append(replace(target, matches=matches))
    return scanned


def plan_prompts(
    source: Path,
    targets: List[PromptTarget],
    selected: Optional[Set[str]] = None,
) -> Plan:
    plan = Plan("prompts")
    content = _content_of(source)
    if content is None:
        plan.warnings.append(
            "No canonical prompt file at {}. Seed it with: prompts capture --from <agent-id>".format(
                source
            )
        )
        return plan
    claimed = {}
    for target in targets:
        if selected and target.id not in selected:
            continue
        current = _content_of(target.path)
        if current is not None and normalize(current) == normalize(render(content, target.style)):
            continue
        key = target.path.resolve()
        if key in claimed:
            plan.warnings.append(
                "{} and {} share one prompt file; one write covers both.".format(
                    claimed[key], target.display_name
                )
            )
            continue
        claimed[key] = target.display_name
        plan.actions.append(
            Action(
                target.id,
                target.path.name,
                source,
                target.path,
                target.style,
                replace=current is not None,
            )
        )
    return plan


def apply_prompts(plan: Plan, source: Path, allowed: Iterable[Path], backup_root: Path) -> None:
    """Write the planned prompt files, backing up anything they replace."""
    root = source.resolve()
    allowed_keys = {path.resolve() for path in allowed}
    content = source.read_text(encoding="utf-8") if source.is_file() else None
    if content is None:
        raise FileNotFoundError("Canonical prompt file disappeared: {}".format(source))
    for action in plan.actions:
        if action.source.resolve() != root:
            raise ValueError(
                "Refusing source outside the canonical prompt file: {}".format(action.source)
            )
        if action.destination.resolve() not in allowed_keys:
            raise ValueError(
                "Refusing destination outside known prompt targets: {}".format(action.destination)
            )
        old = None
        if action.destination.is_file() or action.destination.is_symlink():
            old = backup(action.destination, backup_root / action.agent_id)
        try:
            action.destination.parent.mkdir(parents=True, exist_ok=True)
            action.destination.write_bytes(render(content, action.mode).encode("utf-8"))
        except Exception:
            if old is not None and not action.destination.exists():
                old.replace(action.destination)
            raise
        if old:
            plan.backups.append(old)
    plan.applied = True


def capture_prompt(origin: Path, canonical: Path, backup_root: Path) -> Optional[Path]:
    """Seed the canonical prompt from one host's existing instruction file."""
    content = origin.read_text(encoding="utf-8")
    old = None
    if canonical.is_file():
        old = backup(canonical, backup_root)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes((normalize(content) + "\n").encode("utf-8"))
    return old
