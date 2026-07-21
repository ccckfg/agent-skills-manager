---
name: agent-skills-manager
description: "Inspect and synchronize local Skills with agent-skills-manager. Use when listing, comparing, importing, or syncing Skills across Claude Code, Codex, Cursor, or Antigravity, or when safely reviewing their MCP and agent configuration."
---

# Agent Skills Manager

Use this skill for local agent setup. Manage **Skills files only** through the `agent-skills-manager` CLI or its TUI. Do not manually copy, delete, or rewrite Skill directories.

## Choose the operation

- Start by running `agent-skills-manager --help`; use the installed command names and flags, not guessed syntax.
- Use the CLI for scripted inspection, comparison, synchronization, or a dry-run/plan.
- Use the TUI for interactive inventory review and explicit selection.
- Read the relevant host reference before inspecting or modifying a host: `references/claude-code.md`, `references/codex.md`, `references/cursor.md`, or `references/antigravity.md`.
- If the requested host, config path, format, or command is uncertain or may have changed, consult that product's official documentation before acting.

## Skills workflow

1. Confirm the source, destination agents, and whether the user wants inspect, plan, or apply.
2. Run the manager to inspect inventory and show the proposed changes.
3. For a write, present the exact affected Skills and request confirmation if scope was not already explicit.
4. Run the manager's supported sync/apply command or complete the operation in the TUI.
5. Re-run inspection to verify the intended Skills are present and unrelated Skills were preserved.

Never use the manager to infer permission to modify MCP servers, model settings, hooks, extensions, or other agent configuration.

## MCP and other configuration workflow

Handle MCP and non-Skill configuration through the agent's prompt-guided safe edit process, not Skill synchronization:

1. Read the active configuration and identify the exact target block.
2. Confirm the target host, file, profile/project scope, and intended change with the user when not explicit.
3. Show a minimal diff before applying it.
4. Create a timestamped backup beside the configuration file.
5. Edit only the target block; preserve ordering, comments, and unrelated entries.
6. Validate the native format and any available host command.
7. Re-read the file and report the final target block and backup path.

Do not expose secrets. Ask before replacing credentials, deleting entries, changing a global configuration, or editing an unrecognized format.

## References

Load only the host reference needed for the requested operation.
