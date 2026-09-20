"""Constants and enums for the TUI prompt editor and Vim engine."""

from enum import Enum


class VimMode(str, Enum):
    NORMAL = "NORMAL"
    INSERT = "INSERT"
    COMMAND = "COMMAND"


# Widget IDs
ID_VIM_TEXT_AREA = "prompt-view-text"
ID_STATUS_BAR = "editor-status-bar"
ID_MODE_BADGE = "editor-mode-badge"
ID_SAVE_BUTTON = "editor-save-btn"
ID_CLOSE_BUTTON = "editor-close-btn"
ID_MODE_BUTTON = "editor-mode-btn"
ID_CMD_INPUT = "editor-cmd-input"
ID_STATUS_INFO = "editor-status-info"
ID_CURSOR_INFO = "editor-cursor-info"

# Vim Ex Commands
CMD_WRITE = "w"
CMD_QUIT = "q"
CMD_WRITE_QUIT = "wq"
CMD_WRITE_QUIT_ALT = "x"
CMD_FORCE_QUIT = "q!"

# UI Labels & Messages
LABEL_MODIFIED = "[已修改]"
LABEL_SAVED = "已保存"
MSG_SAVE_SUCCESS = "文件已保存"
MSG_SAVE_FAILED = "保存失败: {error}"
MSG_UNSAVED_WARNING = "存在未保存的修改，请使用 :q! 强制退出或点击保存"
MSG_UNKNOWN_COMMAND = "未知命令: {cmd}"
