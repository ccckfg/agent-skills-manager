"""Presentation-only grouping for large Skill collections."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class SkillGroup:
    key: str
    label: str
    names: tuple[str, ...]


def group_skill_names(names: Iterable[str], minimum_family_size: int = 2) -> tuple[SkillGroup, ...]:
    """Group repeated ``prefix-`` or ``prefix:`` families, then collect the rest."""
    visible = sorted(
        {name for name in names if name and not name.startswith(".")}, key=str.casefold
    )
    prefixes = {name: _prefix(name) for name in visible}
    counts = Counter(prefix for prefix in prefixes.values() if prefix)
    family_prefixes = {prefix for prefix, count in counts.items() if count >= minimum_family_size}

    grouped: list[SkillGroup] = []
    for prefix in sorted(family_prefixes, key=str.casefold):
        members = tuple(name for name in visible if prefixes[name] == prefix)
        grouped.append(SkillGroup(prefix, f"{prefix} 系列", members))

    standalone = tuple(name for name in visible if prefixes[name] not in family_prefixes)
    if standalone:
        grouped.append(SkillGroup("other", "其他 Skills", standalone))
    return tuple(grouped)


def _prefix(name: str) -> str | None:
    positions = [(name.find(separator), separator) for separator in ("-", ":")]
    positions = [(position, separator) for position, separator in positions if position > 0]
    if not positions:
        return None
    position, separator = min(positions)
    return f"{name[:position]}{separator}"
