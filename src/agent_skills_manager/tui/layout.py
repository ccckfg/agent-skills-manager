"""Responsive layout policy for terminal-sized screens."""

from __future__ import annotations

from enum import StrEnum


COMPACT_MAX_HEIGHT = 28


class DetailLayout(StrEnum):
    FULL = "full"
    COMPACT = "compact"


def detail_layout(height: int) -> DetailLayout:
    """Choose a density without coupling layout policy to Textual widgets."""
    return DetailLayout.COMPACT if height <= COMPACT_MAX_HEIGHT else DetailLayout.FULL
