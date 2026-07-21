# Bundled script commands

Set `<run>` to the available Python command followed by the absolute script path, for example:

```text
python3 /path/to/agent-skills-manager/scripts/asm.py
python C:\path\to\agent-skills-manager\scripts\asm.py
py -3 C:\path\to\agent-skills-manager\scripts\asm.py
```

Always quote the script path when it contains spaces.

## Runtime check

```text
<run> doctor --json
```

## Inventory

```text
<run> status --json
<run> status --agent codex --json
<run> status --central /custom/skills --json
```

`status` reads Skills directories and MCP server names. It does not write files.

## Compare Skills

```text
<run> diff --agent codex --json
<run> diff --agent codex --skill frontend-design --json
<run> diff --agent codex --all --json
```

`diff` is read-only. It classifies Skills as `missing`, `extra`, `different`, or
`identical`. For a changed Skill, `files` classifies each path as `only-central`,
`only-agent`, `modified`, or `type-changed`. Identical Skills are omitted from the
`skills` array unless `--all` is supplied, but they are always counted in `summary`.
Repeat `--skill` to compare more than one named Skill.

## Import unmanaged Skills

Preview:

```text
<run> import --agent codex --json
```

Apply the same plan after confirmation:

```text
<run> import --agent codex --json --apply
```

Import always copies into the central directory. A name already claimed during the plan is skipped with a warning.

## Synchronize from the central directory

Preview Copy mode:

```text
<run> sync --agent cursor --mode copy --json
```

Preview Link mode:

```text
<run> sync --agent codex --mode link --json
```

Apply by adding `--apply` to the exact reviewed command:

```text
<run> sync --agent codex --mode link --json --apply
```

Repeat `--agent` to select multiple hosts. Omit it to select all defined hosts. Antigravity changes Link to Copy and emits a warning.

## Agent IDs

- `claude-code`
- `codex`
- `cursor`
- `antigravity`

## Output contract

- JSON plans contain `operation`, `applied`, `actions`, `warnings`, and `backups`.
- JSON diff results contain per-agent `summary` and `skills` arrays with file-level changes.
- A plan without `--apply` has `applied: false` and changes no files.
- Each action contains `agent`, `skill`, `source`, `destination`, `mode`, and `replace`.
- After `--apply`, inspect `backups` and re-run `status --json`.
