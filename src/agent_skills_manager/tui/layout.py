"""Responsive layout policy for terminal-sized screens."""

from __future__ import annotations

from enum import StrEnum


COMPACT_MAX_HEIGHT = 36
TINY_MAX_HEIGHT = 22


class DetailLayout(StrEnum):
    FULL = "full"
    COMPACT = "compact"
    TINY = "tiny"


def detail_layout(height: int) -> DetailLayout:
    """Choose a density without coupling layout policy to Textual widgets."""
    if height <= TINY_MAX_HEIGHT:
        return DetailLayout.TINY
    if height <= COMPACT_MAX_HEIGHT:
        return DetailLayout.COMPACT
    return DetailLayout.FULL
