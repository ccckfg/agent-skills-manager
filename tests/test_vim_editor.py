"""Tests for the Vim editor engine, widgets, and prompt editor screen."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button

from agent_skills_manager.tui.constants import (
    ID_FORCE_QUIT_BUTTON,
    ID_MODE_BUTTON,
    ID_SAVE_BUTTON,
    ID_VIM_TEXT_AREA,
    VimMode,
)
from agent_skills_manager.tui.screens.prompt_editor import PromptEditorScreen
from agent_skills_manager.tui.vim_engine import VimEngine
from agent_skills_manager.tui.widgets.vim_editor import VimTextArea


def test_vim_engine_modes_and_transitions() -> None:
    engine = VimEngine()
    assert engine.mode == VimMode.NORMAL

    # Transition to insert mode
    res = engine.handle_key("i", True, "i")
    assert res.action == "enter_insert"
    assert engine.mode == VimMode.INSERT

    # Escape back to normal
    res = engine.handle_key("escape", False)
    assert res.action == "enter_normal"
    assert engine.mode == VimMode.NORMAL

    # Command mode transition
    res = engine.handle_key(":", True, ":")
    assert res.action == "enter_command"
    assert engine.mode == VimMode.COMMAND

    # Typing in command mode
    res = engine.handle_key("w", True, "w")
    assert res.action == "update_command"
    assert res.param == "w"

    # Enter to execute command
    res = engine.handle_key("enter", False)
    assert res.action == "exec_command"
    assert res.param == "w"
    assert engine.mode == VimMode.NORMAL


def test_vim_engine_multi_key_sequences() -> None:
    engine = VimEngine()

    # dd -> delete_line
    res1 = engine.handle_key("d", True, "d")
    assert res1.action == "pending_key"
    assert res1.param == "d"
    res2 = engine.handle_key("d", True, "d")
    assert res2.action == "delete_line"

    # yy -> yank_line
    res1 = engine.handle_key("y", True, "y")
    assert res1.action == "pending_key"
    res2 = engine.handle_key("y", True, "y")
    assert res2.action == "yank_line"

    # gg -> move_doc_start
    res1 = engine.handle_key("g", True, "g")
    assert res1.action == "pending_key"
    res2 = engine.handle_key("g", True, "g")
    assert res2.action == "move_doc_start"


def test_vim_engine_navigation_keys() -> None:
    engine = VimEngine()
    assert engine.handle_key("h", True, "h").action == "move_left"
    assert engine.handle_key("j", True, "j").action == "move_down"
    assert engine.handle_key("k", True, "k").action == "move_up"
    assert engine.handle_key("l", True, "l").action == "move_right"
    assert engine.handle_key("w", True, "w").action == "move_word_right"
    assert engine.handle_key("b", True, "b").action == "move_word_left"
    assert engine.handle_key("0", True, "0").action == "move_line_start"
    assert engine.handle_key("$", True, "$").action == "move_line_end"
    assert engine.handle_key("G", True, "G").action == "move_doc_end"
    assert engine.handle_key("u", True, "u").action == "undo"
    assert engine.handle_key("ctrl+r", False).action == "redo"


class EditorTestApp(App[None]):
    CSS_PATH = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "agent_skills_manager"
        / "tui"
        / "theme.tcss"
    )

    def __init__(self, screen: PromptEditorScreen) -> None:
        super().__init__()
        self.editor_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.editor_screen)


@pytest.mark.asyncio
async def test_prompt_editor_gui_save_and_mode_toggle() -> None:
    saved_files: list[tuple[Path, str]] = []

    def mock_save(path: Path, content: str) -> None:
        saved_files.append((path, content))

    screen = PromptEditorScreen(
        title="Test Prompt",
        content="line 1\nline 2",
        path=Path("/tmp/test.md"),
        save_handler=mock_save,
    )
    app = EditorTestApp(screen)

    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()
        editor = screen.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        mode_btn = screen.query_one(f"#{ID_MODE_BUTTON}", Button)
        save_btn = screen.query_one(f"#{ID_SAVE_BUTTON}", Button)

        assert editor.mode == VimMode.NORMAL
        assert "NORMAL" in str(mode_btn.label)

        # Press Mode button to switch to INSERT mode
        mode_btn.press()
        await pilot.pause()
        assert editor.mode == VimMode.INSERT
        assert "INSERT" in str(mode_btn.label)

        # Type some text
        await pilot.press("x")
        await pilot.pause()
        assert editor.is_dirty

        # Press Save button
        save_btn.press()
        await pilot.pause()
        assert not editor.is_dirty
        assert len(saved_files) == 1
        assert saved_files[0][0] == Path("/tmp/test.md")
        assert "x" in saved_files[0][1]


@pytest.mark.asyncio
async def test_prompt_editor_vim_command_save_and_quit() -> None:
    saved_files: list[tuple[Path, str]] = []

    def mock_save(path: Path, content: str) -> None:
        saved_files.append((path, content))

    screen = PromptEditorScreen(
        title="Test Prompt",
        content="hello world",
        path=Path("/tmp/test.md"),
        save_handler=mock_save,
    )
    app = EditorTestApp(screen)

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        # Type :w to save
        await pilot.press("colon")
        await pilot.press("w")
        await pilot.press("enter")
        await pilot.pause()
        assert len(saved_files) == 1
        assert saved_files[0][1] == "hello world"

        # Type :q to quit
        await pilot.press("colon")
        await pilot.press("q")
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, PromptEditorScreen)


@pytest.mark.asyncio
async def test_prompt_editor_gui_force_quit_with_unsaved_changes() -> None:
    screen = PromptEditorScreen(
        title="Test Prompt",
        content="hello",
        path=Path("/tmp/test.md"),
    )
    app = EditorTestApp(screen)

    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()
        editor = screen.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        force_btn = screen.query_one(f"#{ID_FORCE_QUIT_BUTTON}", Button)

        # Make it dirty
        editor.text = "modified content"
        editor.check_dirty()
        assert editor.is_dirty

        # Click force quit button
        force_btn.press()
        await pilot.pause()
        assert not isinstance(app.screen, PromptEditorScreen)


@pytest.mark.asyncio
async def test_prompt_editor_vim_force_quit_command() -> None:
    screen = PromptEditorScreen(
        title="Test Prompt",
        content="hello",
        path=Path("/tmp/test.md"),
    )
    app = EditorTestApp(screen)

    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()
        editor = screen.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)

        # Make it dirty
        editor.text = "modified content"
        editor.check_dirty()
        assert editor.is_dirty

        # Type :q! to force quit
        await pilot.press("colon")
        await pilot.press("q")
        await pilot.press("exclamation_mark")
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, PromptEditorScreen)
