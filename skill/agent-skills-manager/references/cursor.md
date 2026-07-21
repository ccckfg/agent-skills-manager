# Cursor

Load when the request names Cursor, workspace rules, project/user settings, extensions, or Cursor MCP configuration.

First identify whether the request targets a workspace or user profile. Use the manager only to synchronize Skills. Do not treat rules, MCP entries, extensions, or editor settings as Skills. Cursor's config paths, precedence, and schemas are version-dependent; inspect the installed configuration and consult official Cursor documentation when uncertain.

For any non-Skill edit, read the exact configuration, confirm scope and target entry, show a minimal diff, make a timestamped sibling backup, change only the target entry, validate the native format, and re-read it. Keep unrelated rules, settings, and credentials intact.
