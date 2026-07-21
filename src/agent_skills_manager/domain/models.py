from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class SyncMode(StrEnum):
    LINK = "link"
    COPY = "copy"


class ItemStatus(StrEnum):
    READY = "ready"
    MISSING = "missing"
    DIFFERENT = "different"
    BROKEN = "broken"
    UNMANAGED = "unmanaged"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    id: str
    display_name: str
    skills_paths: dict[str, str]
    mcp_paths: dict[str, str]
    mcp_format: str
    supports_link: bool = True


@dataclass(slots=True)
class AgentPreference:
    enabled: bool = True
    skills_mode: SyncMode = SyncMode.COPY


@dataclass(frozen=True, slots=True)
class SkillEntry:
    name: str
    path: Path
    status: ItemStatus = ItemStatus.READY
    is_link: bool = False


@dataclass(frozen=True, slots=True)
class McpEntry:
    name: str
    config_path: Path


@dataclass(slots=True)
class AgentInventory:
    definition: AgentDefinition
    installed: bool
    skills_path: Path
    mcp_path: Path
    preference: AgentPreference
    skills: list[SkillEntry] = field(default_factory=list)
    mcps: list[McpEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.errors) or any(item.status is not ItemStatus.READY for item in self.skills)


@dataclass(slots=True)
class InventorySnapshot:
    agents: list[AgentInventory]
    central_skills_path: Path

    def agent(self, agent_id: str) -> AgentInventory | None:
        return next(
            (item for item in self.agents if item.definition.id == agent_id),
            None,
        )


@dataclass(frozen=True, slots=True)
class SyncAction:
    agent_id: str
    skill_name: str
    source: Path
    destination: Path
    mode: SyncMode
    replace: bool = False


@dataclass(slots=True)
class SyncPlan:
    actions: list[SyncAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.actions)
