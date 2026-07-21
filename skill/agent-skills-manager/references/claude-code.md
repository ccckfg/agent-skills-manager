# Claude Code

Load when the request names Claude Code, `~/.claude`, project instructions, or Claude MCP settings.

Find configuration by checking the requested project scope first, then the active user scope. Treat Skill locations and MCP configuration as separate concerns. Paths, precedence, and file formats can change; verify them in Claude Code's official documentation when they are not already evident in the local installation.

Use `agent-skills-manager` CLI/TUI only for Skills. For MCP or other settings, read the exact active file, confirm scope, show the minimal diff, create a timestamped sibling backup, edit only the named block, validate the native format, then re-read it. Never overwrite unrelated project instructions, permissions, hooks, or credentials.
