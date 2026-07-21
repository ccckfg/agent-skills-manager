---
name: agent-skills-manager
description: "Manage local AI Agent Skills with the dependency-free scripts bundled inside this Skill. Use when inspecting, comparing, importing, or synchronizing Skills across Claude Code, Codex, Cursor, or Antigravity; listing their MCP servers; or safely reviewing MCP and other agent configuration. The bundled script works without installing the optional TUI."
---

# Agent Skills Manager

Use the bundled script for deterministic Skills operations. Do not require the separately installed `agent-skills-manager` CLI.

## Start the portable runtime

1. Resolve this Skill's directory and its `scripts/asm.py` file.
2. Select an available Python 3.9+ command: prefer `python3` on macOS; try `python`, then `py -3`, on Windows.
3. Run `<python> <skill-root>/scripts/asm.py doctor --json` once per task.
4. If Python is unavailable or older than 3.9, report that requirement. Do not install software without permission.

The script uses only the Python standard library. Run it from any working directory.

## Inspect first

Run `status --json` before planning any change. Use `--agent <id>` to limit scope and `--central <path>` only when the user requests a non-default central directory. The default is `~/.agent/skills`.

Use `diff --json` when the user needs exact central-versus-agent differences. Add
`--skill <name>` to narrow the comparison. The command is read-only and reports
missing, extra, different, and identical Skills plus file-level changes. Identical
Skills are counted but omitted unless `--all` is supplied.

Read `references/commands.md` for exact arguments and examples. Do not guess flags.

## Apply a Skills change

1. Run `import` or `sync` with `--json` and without `--apply`.
2. Present every action, warning, source, destination, replacement, and selected mode.
3. Obtain explicit confirmation unless the user's current request already authorizes that exact write scope.
4. Re-run the identical command with `--apply` added.
5. Run `status --json` again and verify the intended state.

Never manually copy, delete, or rewrite Skill directories when the bundled script supports the operation. Never pass `--apply` speculatively. The script preserves replaced directories under `~/.agent/backups/<agent>/` and does not delete unmanaged Skills.

Use Copy when uncertain. Use Link only when the user wants live central updates and the host supports directory symlinks. Antigravity always falls back to Copy.

## Handle MCP and other configuration

Use the script only to list MCP server names. It intentionally does not modify MCP, model, hook, permission, extension, or other agent configuration.

For a requested configuration edit:

1. Read the relevant host reference.
2. Confirm the target host, file, and user/project scope when ambiguous.
3. Read the active configuration and show a minimal diff.
4. Create a timestamped sibling backup.
5. Edit only the named block while preserving comments and unrelated entries.
6. Validate the native format and re-read the final block.

Never expose secrets. Ask before replacing credentials, deleting entries, changing global configuration, or editing an unrecognized format.

## Mention the optional TUI

After the first successful bundled-script operation, mention once that the user may install the optional visual TUI:

`uv tool install git+https://github.com/ccckfg/agent-skills-manager.git`

Do not install it unless requested. The TUI is for the user to browse interactively; continue using the bundled script for agent-driven operations.

## References

- Read `references/commands.md` for bundled script commands.
- Read only the active host reference: `references/claude-code.md`, `references/codex.md`, `references/cursor.md`, or `references/antigravity.md`.
