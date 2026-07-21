from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AgentProfile:
    id: str
    display_name: str
    skills_path: Path
    mcp_path: Path
    mcp_format: str
    supports_link: bool = True


@dataclass(frozen=True)
class SkillRecord:
    name: str
    path: Path
    status: str
    is_link: bool = False

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "status": self.status,
            "is_link": self.is_link,
        }


@dataclass
class AgentInventory:
    profile: AgentProfile
    installed: bool
    skills: List[SkillRecord] = field(default_factory=list)
    mcps: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.errors) or any(item.status != "ready" for item in self.skills)

    def as_dict(self) -> Dict[str, object]:
        return {
            "id": self.profile.id,
            "agent": self.profile.display_name,
            "installed": self.installed,
            "skills_path": str(self.profile.skills_path),
            "mcp_path": str(self.profile.mcp_path),
            "skills": [item.as_dict() for item in self.skills],
            "mcps": self.mcps,
            "errors": self.errors,
            "attention": self.needs_attention,
        }


@dataclass(frozen=True)
class Action:
    agent_id: str
    skill_name: str
    source: Path
    destination: Path
    mode: str
    replace: bool = False

    def as_dict(self) -> Dict[str, object]:
        return {
            "agent": self.agent_id,
            "skill": self.skill_name,
            "source": str(self.source),
            "destination": str(self.destination),
            "mode": self.mode,
            "replace": self.replace,
        }


@dataclass
class Plan:
    operation: str
    actions: List[Action] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    applied: bool = False
    backups: List[Path] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "operation": self.operation,
            "applied": self.applied,
            "actions": [action.as_dict() for action in self.actions],
            "warnings": self.warnings,
            "backups": [str(path) for path in self.backups],
        }


@dataclass(frozen=True)
class FileDifference:
    path: str
    status: str

    def as_dict(self) -> Dict[str, str]:
        return {"path": self.path, "status": self.status}


@dataclass
class SkillDifference:
    name: str
    status: str
    central_path: Optional[Path]
    agent_path: Optional[Path]
    agent_is_link: bool = False
    files: List[FileDifference] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "central_path": str(self.central_path) if self.central_path else None,
            "agent_path": str(self.agent_path) if self.agent_path else None,
            "agent_is_link": self.agent_is_link,
            "files": [item.as_dict() for item in self.files],
        }


@dataclass
class AgentDifference:
    profile: AgentProfile
    skills: List[SkillDifference] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        statuses = ("identical", "missing", "extra", "different")
        return {status: sum(item.status == status for item in self.skills) for status in statuses}

    def as_dict(self, include_identical: bool = False) -> Dict[str, object]:
        visible = (
            self.skills
            if include_identical
            else [item for item in self.skills if item.status != "identical"]
        )
        return {
            "id": self.profile.id,
            "agent": self.profile.display_name,
            "skills_path": str(self.profile.skills_path),
            "summary": self.summary,
            "skills": [item.as_dict() for item in visible],
        }


def find_agent(inventories: List[AgentInventory], agent_id: str) -> Optional[AgentInventory]:
    return next((item for item in inventories if item.profile.id == agent_id), None)
