from agent_skills_manager.tui.layout import COMPACT_MAX_HEIGHT, DetailLayout, detail_layout


def test_detail_layout_uses_compact_mode_at_height_threshold() -> None:
    assert detail_layout(COMPACT_MAX_HEIGHT - 1) is DetailLayout.COMPACT
    assert detail_layout(COMPACT_MAX_HEIGHT) is DetailLayout.COMPACT
    assert detail_layout(COMPACT_MAX_HEIGHT + 1) is DetailLayout.FULL
