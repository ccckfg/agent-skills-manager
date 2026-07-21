import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import AgentDifference, AgentProfile, FileDifference, SkillDifference
from .store import child_directories, is_link


IGNORED_DIRECTORY_NAMES = {"__pycache__"}
IGNORED_FILE_NAMES = {".DS_Store"}
IGNORED_FILE_SUFFIXES = {".pyc"}

Entry = Tuple[str, str]


def _ignored(path: Path) -> bool:
    return (
        path.name in IGNORED_DIRECTORY_NAMES
        or path.name in IGNORED_FILE_NAMES
        or path.suffix in IGNORED_FILE_SUFFIXES
    )


def _file_digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _entries(root: Path) -> Dict[str, Entry]:
    entries = {}

    def visit(directory: Path) -> None:
        for item in sorted(directory.iterdir(), key=lambda value: value.name.lower()):
            if _ignored(item):
                continue
            relative = item.relative_to(root).as_posix()
            if is_link(item):
                try:
                    target = str(item.readlink())
                except (OSError, AttributeError):
                    target = str(item.resolve(strict=False))
                entries[relative] = ("link", target)
            elif item.is_dir():
                entries[relative] = ("directory", "")
                visit(item)
            elif item.is_file():
                entries[relative] = ("file", _file_digest(item))

    if root.is_dir():
        visit(root)
    return entries


def _file_differences(central: Path, agent: Path) -> List[FileDifference]:
    central_entries = _entries(central)
    agent_entries = _entries(agent)
    differences = []
    for path in sorted(set(central_entries) | set(agent_entries), key=str.lower):
        central_entry = central_entries.get(path)
        agent_entry = agent_entries.get(path)
        if central_entry is None:
            status = "only-agent"
        elif agent_entry is None:
            status = "only-central"
        elif central_entry[0] != agent_entry[0]:
            status = "type-changed"
        elif central_entry != agent_entry:
            status = "modified"
        else:
            continue
        differences.append(FileDifference(path, status))
    return differences


def _one_agent(
    central_skills: Dict[str, Path],
    profile: AgentProfile,
    skill_names: Optional[Set[str]],
) -> AgentDifference:
    agent_skills = child_directories(profile.skills_path)
    names = set(central_skills) | set(agent_skills)
    if skill_names is not None:
        names &= skill_names
    skills = []
    for name in sorted(names, key=str.lower):
        central = central_skills.get(name)
        agent = agent_skills.get(name)
        if central is None:
            status, files = "extra", []
        elif agent is None:
            status, files = "missing", []
        else:
            files = _file_differences(central, agent)
            status = "different" if files else "identical"
        skills.append(
            SkillDifference(
                name=name,
                status=status,
                central_path=central,
                agent_path=agent,
                agent_is_link=is_link(agent) if agent else False,
                files=files,
            )
        )
    return AgentDifference(profile, skills)


def compare(
    central: Path,
    profiles: Iterable[AgentProfile],
    skill_names: Optional[Set[str]] = None,
) -> List[AgentDifference]:
    central_skills = child_directories(central)
    return [_one_agent(central_skills, profile, skill_names) for profile in profiles]
