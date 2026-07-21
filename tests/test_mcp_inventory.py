from agent_skills_manager.infrastructure.mcp_reader import McpReader


def test_reader_handles_jsonc_comments_and_trailing_comma(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text('{ // keep url strings\n "mcpServers": {"one": {"url": "https://x"},}, }')
    assert McpReader().server_names(path, "jsonc") == ["one"]


def test_reader_handles_codex_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[mcp_servers.alpha]\ncommand = "a"\n[mcp_servers.beta]\ncommand = "b"')
    assert McpReader().server_names(path, "toml") == ["alpha", "beta"]
