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
<run> status --verify --json
```

`status` reads Skills directories and MCP server names. It does not write files.

By default `status` reports presence and link health only, and the payload carries
`"verified": false`. A Skill that exists under a different version still reports
`ready`. Add `--verify` to hash file contents, or use `diff` for the exact change
set. Prefer the default: with every supported host defined, verification re-reads
every managed Skill in every installed host.

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

`claude-code`, `codex`, `cursor`, `antigravity`, `gemini-cli`, `copilot-cli`,
`windsurf`, `opencode`, `kiro`, `pi`, `droid`, `qoder`, `qoder-cn`, `trae`,
`trae-cn`, `codebuddy`, `kimi-code`, `iflow`, `qwen-code`, `lingma`,
`mimo-code`, `agents-shared`.

`--agent` rejects an unknown ID, so read the error rather than guessing a name.
See `references/agents.md` for each host's directories and quirks.

## Output contract

- JSON status results contain `central`, `verified`, and `agents`.
- Each agent carries `present` and `missing` counts alongside the full `skills` array.
- `attention` means a state the user must resolve: a broken link, an unmanaged Skill,
  a read error, or — only when contents were compared — a Skill that differs. A Skill
  the central store has but the host does not is reported in `missing`, never as
  `attention`. Do not describe a `missing` count as a problem.
- JSON plans contain `operation`, `applied`, `actions`, `warnings`, and `backups`.
- JSON diff results contain per-agent `summary` and `skills` arrays with file-level changes.
- A plan without `--apply` has `applied: false` and changes no files.
- Each action contains `agent`, `skill`, `source`, `destination`, `mode`, and `replace`.
- After `--apply`, inspect `backups` and re-run `status --json`.
