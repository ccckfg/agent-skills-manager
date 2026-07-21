"""Scrollable, grouped, multi-select Skill tree."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree

from agent_skills_manager.domain.models import ItemStatus, SkillEntry
from agent_skills_manager.tui.grouping import SkillGroup, group_skill_names


@dataclass(frozen=True, slots=True)
class SkillNodeData:
    names: tuple[str, ...]
    is_group: bool = False


class SkillTree(Tree[SkillNodeData]):
    """A grouped Tree where Space checks leaves or an entire family."""

    BINDINGS = [
        Binding("space", "toggle_checked", "选择", priority=True),
        Binding("enter", "toggle_group", "展开", show=False),
    ]

    class SelectionChanged(Message):
        def __init__(self, tree: SkillTree) -> None:
            self.tree = tree
            super().__init__()

        @property
        def control(self) -> SkillTree:
            return self.tree

    def __init__(self, title: str, *, id: str) -> None:
        super().__init__(title, id=id)
        self.title = title
        self.show_root = False
        self.guide_depth = 3
        self.auto_expand = False
        self._entries: dict[str, SkillEntry] = {}
        self._checked: set[str] = set()
        self._skill_nodes: dict[str, Any] = {}
        self._group_nodes: list[tuple[Any, SkillGroup]] = []

    @property
    def selected_skill(self) -> str | None:
        data = self.cursor_node.data if self.cursor_node else None
        if data and not data.is_group and len(data.names) == 1:
            return data.names[0]
        return None

    @property
    def selected_names(self) -> tuple[str, ...]:
        return tuple(name for name in self._entries if name in self._checked)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def highlighted_names(self) -> tuple[str, ...]:
        data = self.cursor_node.data if self.cursor_node else None
        return data.names if data else ()

    def entry(self, name: str | None) -> SkillEntry | None:
        return self._entries.get(name) if name else None

    def select_skill(self, name: str) -> bool:
        node = self._skill_nodes.get(name)
        if node is None:
            return False
        if node.parent:
            node.parent.expand()
        self.call_after_refresh(self._move_to_node, node)
        return True

    def _move_to_node(self, node: Any) -> None:
        self.move_cursor(node)
        self.scroll_to_node(node)

    def load_entries(self, entries: Sequence[SkillEntry], empty_message: str) -> None:
        previous = self.selected_skill
        self._entries = {entry.name: entry for entry in entries if not entry.name.startswith(".")}
        self._checked.intersection_update(self._entries)
        self._skill_nodes = {}
        self._group_nodes = []
        self.reset(self.title)
        self.root.expand()
        if not self._entries:
            self.root.add_leaf(Text(empty_message, style="dim"))
            self.move_cursor(self.root)
            return

        first_visible = None
        for group in group_skill_names(self._entries):
            expanded = len(group.names) <= 8
            data = SkillNodeData(group.names, is_group=True)
            group_node = self.root.add(self._group_label(group), data=data, expand=expanded)
            self._group_nodes.append((group_node, group))
            for name in group.names:
                entry = self._entries[name]
                node = group_node.add_leaf(
                    self._skill_label(entry),
                    data=SkillNodeData((name,)),
                )
                self._skill_nodes[name] = node
                if expanded and first_visible is None:
                    first_visible = node

        cursor = self._skill_nodes.get(previous) or first_visible or self.root.children[0]
        self.move_cursor(cursor)

    def action_toggle_checked(self) -> None:
        names = self.highlighted_names
        if not names:
            return
        if all(name in self._checked for name in names):
            self._checked.difference_update(names)
        else:
            self._checked.update(names)
        self._refresh_labels()
        self.post_message(self.SelectionChanged(self))

    def action_toggle_group(self) -> None:
        node = self.cursor_node
        if node and node.data and node.data.is_group:
            node.toggle()

    def _refresh_labels(self) -> None:
        for name, node in self._skill_nodes.items():
            node.set_label(self._skill_label(self._entries[name]))
        for node, group in self._group_nodes:
            node.set_label(self._group_label(group))
        self.refresh()

    def _skill_label(self, entry: SkillEntry) -> Text:
        checked = entry.name in self._checked
        mark = "●" if checked else "○"
        details = []
        if entry.is_link:
            details.append("link")
        if entry.status not in {ItemStatus.READY, ItemStatus.MISSING}:
            details.append(entry.status.value)
        suffix = f"  {' · '.join(details)}" if details else ""
        return Text.assemble(
            (mark, "bold" if checked else "dim"), "  ", entry.name, (suffix, "dim")
        )

    def _group_label(self, group: SkillGroup) -> Text:
        selected = sum(name in self._checked for name in group.names)
        mark = "○" if selected == 0 else ("●" if selected == len(group.names) else "◐")
        style = "dim" if selected == 0 else "bold"
        return Text.assemble(
            (mark, style),
            "  ",
            (group.label, "bold"),
            (f"  {selected}/{len(group.names)}" if selected else f"  {len(group.names)}", "dim"),
        )
