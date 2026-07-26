from agent_skills_manager.infrastructure.mcp_reader import McpReader


def test_reader_handles_jsonc_comments_and_trailing_comma(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text('{ // keep url strings\n "mcpServers": {"one": {"url": "https://x"},}, }')
    assert McpReader().server_names(path, "jsonc") == ["one"]


def test_reader_handles_codex_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[mcp_servers.alpha]\ncommand = "a"\n[mcp_servers.beta]\ncommand = "b"')
    assert McpReader().server_names(path, "toml") == ["alpha", "beta"]


def test_reader_handles_opencode_style_mcp_block(tmp_path):
    """opencode and its forks put servers directly under the top-level mcp key."""
    path = tmp_path / "opencode.json"
    path.write_text('{"mcp": {"github": {"type": "local"}, "docs": {"type": "remote"}}}')
    assert McpReader().server_names(path, "jsonc") == ["docs", "github"]


def test_reader_ignores_scalar_options_in_an_mcp_settings_block(tmp_path):
    """Gemini-style settings.json uses mcp for options, not for server definitions."""
    path = tmp_path / "settings.json"
    path.write_text('{"mcp": {"allowed": ["a"], "serverCommand": "x"}}')
    assert McpReader().server_names(path, "jsonc") == []


def test_reader_prefers_mcp_servers_over_the_mcp_options_block(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"mcpServers": {"real": {}}, "mcp": {"allowed": ["real"]}}')
    assert McpReader().server_names(path, "jsonc") == ["real"]
