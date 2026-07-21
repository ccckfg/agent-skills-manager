import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set

from .models import AgentInventory, AgentProfile, SkillRecord
from .store import child_directories, equivalent, is_link

try:
    import tomllib
except ImportError:  # Python 3.10 fallback for MCP name discovery.
    tomllib = None


def _strip_json_comments(text: str) -> str:
    output = []
    index, quoted, escaped = 0, False, False
    while index < len(text):
        char = text[index]
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            index += 1
            continue
        if char == '"':
            quoted = True
            output.append(char)
            index += 1
        elif text[index : index + 2] == "//":
            index = text.find("\n", index)
            if index < 0:
                break
        elif text[index : index + 2] == "/*":
            end = text.find("*/", index + 2)
            index = len(text) if end < 0 else end + 2
        else:
            output.append(char)
            index += 1
    return "".join(output)


def _collect_named_tables(value: object, key_name: str) -> Set[str]:
    names = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == key_name and isinstance(child, dict):
                names.update(str(name) for name in child)
            names.update(_collect_named_tables(child, key_name))
    elif isinstance(value, list):
        for child in value:
            names.update(_collect_named_tables(child, key_name))
    return names


def mcp_names(path: Path, format_name: str) -> List[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    if format_name == "toml":
        if tomllib:
            data = tomllib.loads(text)
            return sorted(_collect_named_tables(data, "mcp_servers"))
        pattern = r"^\s*\[mcp_servers\.([^\].]+)\]"
        return sorted(set(re.findall(pattern, text, re.MULTILINE)))
    data = json.loads(_strip_json_comments(text))
    return sorted(_collect_named_tables(data, "mcpServers"))


def _skill_records(
    central: Dict[str, Path],
    local: Dict[str, Path],
    compare_contents: bool = True,
    trust_links: bool = False,
) -> List[SkillRecord]:
    records = []
    remaining = dict(local)
    for name, source in central.items():
        target = remaining.pop(name, None)
        if target is None:
            records.append(SkillRecord(name, source, "missing"))
        elif is_link(target) and not target.exists():
            records.append(SkillRecord(name, target, "broken", True))
        else:
            target_is_link = is_link(target)
            points_to_source = target_is_link and target.resolve() == source.resolve()
            if points_to_source or not compare_contents or (trust_links and target_is_link):
                status = "ready"
            else:
                status = "ready" if equivalent(source, target) else "different"
            records.append(SkillRecord(name, target, status, target_is_link))
    for name, target in remaining.items():
        records.append(SkillRecord(name, target, "unmanaged", is_link(target)))
    return sorted(records, key=lambda item: item.name.lower())


def scan(
    central: Path,
    profiles: Iterable[AgentProfile],
    compare_contents: bool = True,
    trust_links: bool = False,
) -> List[AgentInventory]:
    canonical = child_directories(central)
    inventories = []
    for profile in profiles:
        errors = []
        try:
            servers = mcp_names(profile.mcp_path, profile.mcp_format)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            servers = []
            errors.append("Could not read MCP configuration: {}".format(error))
        inventories.append(
            AgentInventory(
                profile=profile,
                installed=profile.skills_path.exists() or profile.mcp_path.exists(),
                skills=_skill_records(
                    canonical,
                    child_directories(profile.skills_path),
                    compare_contents,
                    trust_links,
                ),
                mcps=servers,
                errors=errors,
            )
        )
    return inventories
