# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```shell
uv sync                      # create .venv and install dev deps
uv run pytest -q             # all 54 tests
uv run pytest tests/test_skill_sync.py::test_sync_plan_can_target_one_selected_skill   # one test
uv run ruff check .
uv run ruff format --check .
uv build

uv run agent-skills-manager init      # write settings.yaml + create ~/.agentskillsbank/skills
uv run agent-skills-manager status --json
uv run agent-skills-manager sync --agent codex --dry-run
uv run agent-skills-manager           # no subcommand => TUI
```

The bundled portable script is run directly, never through uv:

```shell
python skill/agent-skills-manager/scripts/asm.py doctor --json
python skill/agent-skills-manager/scripts/asm.py status --json
python skill/agent-skills-manager/scripts/asm.py sync --agent codex --mode copy --json --apply
```

## Two implementations, on purpose

The repo ships the same domain twice. Do not merge them, and do not import one from the other.

| | `src/agent_skills_manager/` | `skill/agent-skills-manager/scripts/` |
|---|---|---|
| Ships as | optional `uv tool install` CLI + Textual TUI | a Skill directory the user copies into an agent |
| Python | ≥ 3.11 | ≥ 3.9 |
| Deps | textual, pydantic, pyyaml, platformdirs | **stdlib only** |
| Style | `StrEnum`, `X \| None`, slotted dataclasses | `typing.List/Optional/Dict`, plain string statuses (`"missing"`, `"unmanaged"`, …) |
| Write guard | interactive confirmation (`--yes` to skip) | `--apply` flag, plan-only by default |

A change to sync/import/backup semantics normally has to land in both, and both have their own tests (`tests/test_skill_*.py` vs `tests/test_bundled_skill_script.py`, which runs `asm.py` as a subprocess). Anything added to `asm_lib/` must stay importable on 3.9 with no third-party packages — `asm_lib/inventory.py` already carries a `tomllib` fallback for 3.10.

Agent definitions are also duplicated: `src/agent_skills_manager/resources/agents.yaml` and `skill/agent-skills-manager/scripts/agent_profiles.json` — same 21 agents, same key names, same shape. `tests/test_detector.py::test_portable_profiles_match_the_installed_registry` fails if they drift, so edit both, plus the README support table and the table in `skill/.../references/agents.md`.

`skills_paths` / `mcp_paths` map a lowercase `platform.system()` key (or `default`) to **either a path string or a list of candidates**, most preferred first. `AgentDetector` resolves each to the first candidate that exists on this machine and falls back to the first entry, which is how relocated directories (Antigravity's two Skills locations, CodeBuddy's three MCP filenames) keep working. A reported path is therefore machine-dependent — never hardcode one in a test without creating the directory first.

## Architecture (`src/`)

Strict one-way layering — `cli.py` → `services/` → `infrastructure/` + `adapters/` + `config/`, all over `domain/models.py`. `domain/` imports nothing from the project.

- `domain/models.py` — the whole vocabulary: `ItemStatus` (READY / MISSING / DIFFERENT / BROKEN / UNMANAGED / ERROR), `SyncMode`, `SyncAction`, `SyncPlan`, `InventorySnapshot`. Status drives every downstream decision. `needs_attention` deliberately excludes MISSING — not installing a central Skill is a choice, so it is surfaced through `missing_skills` in its own column while only BROKEN / UNMANAGED / DIFFERENT / ERROR (or a read error) demand action. Both implementations must agree on this; the CLI, TUI and portable script all read it.
- `services/inventory.py` — builds the snapshot. `scan(verify_contents=True)` hashes directory contents; `verify_contents=False` reports presence and link health only. **Content hashing scales with agents × skills**, so only sync and import verify: `status` needs `--verify`, and the TUI never does. Skipping it took a real 100-skill store from 353s to 1.1s. Keep new scan callers on the cheap path unless they must prove two directories hold the same bytes.
- `services/skill_sync.py`, `skill_import.py`, `skill_removal.py` — every mutating service splits `plan()` (pure, returns actions + warnings) from `execute()`. `plan()` must never touch the filesystem; callers show the plan before applying.
- `infrastructure/skill_store.py` — the only place that copies, links, hashes, or backs up.
- `infrastructure/mcp_reader.py` — read-only, hand-rolled JSONC comment stripper plus `tomllib`. Understands three shapes: `mcpServers`, `mcp_servers`, and a top-level `mcp` block whose mapping values are servers (opencode and its forks) — scalars in that block are options, not servers. MCP config is never written by this codebase; that is left to the Skill's documented agent-driven workflow.

**The TUI is a pure view.** `tui/` never imports `services/`. `cli._run_tui` closes over the services and passes five callables (`fast_snapshot`, `sync_agent`, `set_mode`, `add_skills`, `remove_skills`) into `run_tui`; `AgentSkillsApp` only knows those handlers. Tests instantiate `AgentSkillsApp(snapshot_fn)` with fabricated snapshots and no filesystem. Keep new behavior on that seam.

Layout and grouping policy live in pure, separately tested modules — `tui/layout.py` (`detail_layout(height)` → FULL/COMPACT/TINY) and `tui/grouping.py` (folds `gsd-`, `gsap-` prefix families into series). Don't inline those rules into widgets.

The detail screen's right pane is a **two-way** diff against the central store, so an UNMANAGED Skill appears in both panes on purpose: it is installed here (left, removable with `D`) and it is a central difference (right, importable with `I`). `SkillTree.load_entries(pinned_names=…)` keeps those in a leading group instead of letting prefix grouping scatter them. `_split_right_selection` drives everything else: it stops `A` from trying to add a Skill the central store cannot supply, and flips the pane's single button between "添加所选" and "导入中央仓库". Tests in `test_tui.py` pin all of it.

The TUI now has four mutation handlers (add / remove / import / sync), all injected from `cli._run_tui`. `test_cli.py::_tui_handlers` captures them by stubbing `agent_skills_manager.tui.run_tui`, which is how the real closures get tested against a sandboxed home rather than a mock.

Inventory loading and mutations run in `@work(thread=True)` workers so first paint is never blocked; results come back via `call_from_thread`.

## Safety invariants

These are load-bearing and covered by tests. Preserve them in both implementations.

- Sync sources must resolve under the central skills directory; `execute()` raises otherwise.
- A destination's basename must equal the skill name (no path traversal via a skill name).
- Refuse to overwrite anything not marked `replace` — that is what protects agent-only unmanaged Skills.
- Replacing an existing Skill first moves the old directory to `~/.agentskillsbank/backups/<agent-id>/<name>-<utc-timestamp>`; if the copy or link then fails, the backup is restored.
- Removal is a move into that same backup area, never a delete.
- Import never overwrites an existing central Skill; a name collision becomes a warning and is skipped.
- A directory counts as a Skill only if it contains `SKILL.md` (or is a link). Dot-directories and `.agent-skills-manager-backup-*` are invisible to every scan.

## Platform notes

Link mode on Windows creates a directory **junction** via `mklink /J` (`COMSPEC`), not a symlink, so it works without developer mode; `SkillStore.is_link` therefore checks symlink, `is_junction`, and the reparse-point attribute. `expand_path` resolves `~` through `HOME`/`USERPROFILE` explicitly — tests set both to `tmp_path` to sandbox scans, so never bypass it with bare `Path.expanduser()`. Antigravity is `supports_link: false`; link plans silently downgrade to copy with a warning. The default central store is `~/.agentskillsbank/skills`; `asm_lib.paths.central_path` and `config.settings.default_central_skills_path` fall back to a legacy `~/.agent/skills` that still exists when the new path does not, and the two implementations must keep agreeing on that choice.

## Conventions

- Code, comments, docstrings, CLI output, and `SKILL.md`/`references/` are English. TUI user-facing strings and README are Chinese.
- ruff, line length 100, target py311.
- Async TUI tests use `@pytest.mark.asyncio` with `app.run_test(size=(120, 32))`, then `await app.workers.wait_for_complete()` before asserting.
