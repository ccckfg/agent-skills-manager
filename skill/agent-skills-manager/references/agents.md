# Supported hosts

Load when the request names a host that has no dedicated reference file, or when you
need the directories, MCP format, or link support for any host.

The script already knows these locations. Read this file to explain a result, not to
build paths by hand. Report a path the script prints; do not assert a path from here
if the script printed a different one.

## Directories

| Agent ID | Product | User Skills | User MCP configuration | Format |
|---|---|---|---|---|
| `claude-code` | Claude Code | `~/.claude/skills` | `~/.claude.json` | JSONC |
| `codex` | Codex | `~/.codex/skills` | `~/.codex/config.toml` | TOML |
| `cursor` | Cursor | `~/.cursor/skills` | `~/.cursor/mcp.json` | JSONC |
| `antigravity` | Antigravity | `~/.gemini/config/skills`, then `~/.gemini/antigravity/skills` | `~/.gemini/antigravity/mcp_config.json` | JSONC |
| `gemini-cli` | Gemini CLI | `~/.gemini/skills` | `~/.gemini/settings.json` | JSONC |
| `copilot-cli` | GitHub Copilot CLI | `~/.copilot/skills` | `~/.copilot/mcp-config.json` | JSONC |
| `windsurf` | Windsurf | `~/.codeium/windsurf/skills` | `~/.codeium/windsurf/mcp_config.json` | JSONC |
| `opencode` | opencode | `~/.config/opencode/skills` | `~/.config/opencode/opencode.jsonc`, then `.json` | JSONC |
| `kiro` | Kiro | `~/.kiro/skills` | `~/.kiro/settings/mcp.json` | JSONC |
| `pi` | Pi | `~/.pi/agent/skills` | `~/.pi/agent/mcp.json`, then `~/.config/mcp/mcp.json` | JSONC |
| `droid` | Droid (Factory) | `~/.factory/skills` | `~/.factory/mcp.json` | JSONC |
| `qoder` | Qoder | `~/.qoder/skills` | `~/.qoder/mcp.json` | JSONC |
| `qoder-cn` | Qoder CN | `~/.qoder-cn/skills` | `~/.qoder-cn/mcp.json` | JSONC |
| `trae` | Trae | `~/.trae/skills` | `~/.trae/mcp.json` | JSONC |
| `trae-cn` | Trae CN | `~/.trae-cn/skills` | `~/.trae-cn/mcp.json` | JSONC |
| `codebuddy` | CodeBuddy | `~/.codebuddy/skills` | `~/.codebuddy/.mcp.json`, then `~/.codebuddy/mcp.json`, then `~/.codebuddy.json` | JSONC |
| `kimi-code` | Kimi Code CLI | `~/.kimi/skills` | `~/.kimi/mcp.json` | JSONC |
| `iflow` | iFlow CLI | `~/.iflow/skills` | `~/.iflow/mcp.json`, then `~/.iflow/settings.json` | JSONC |
| `qwen-code` | Qwen Code | `~/.qwen/skills` | `~/.qwen/settings.json` | JSONC |
| `lingma` | Lingma | `~/.lingma/skills` | `~/.lingma/lingma_mcp.json`, then `~/.lingma/mcp.json` | JSONC |
| `mimo-code` | MiMo Code | `~/.config/mimocode/skills` | `~/.config/mimocode/mimocode.jsonc`, then `.json` | JSONC |
| `agents-shared` | Shared `.agents` directory | `~/.agents/skills`, then `~/.config/agents/skills` | `~/.agents/mcp.json`, then `~/.agents/mcp/mcp.json` | JSONC |

Where several locations are listed, the script uses the first one that exists on this
machine and falls back to the first entry when none do. That is why a reported path can
differ between two machines running the same version.

Only Antigravity is defined as unable to follow a directory link; every other host
accepts Copy or Link. Prefer Copy unless the user asks for live central updates.

## Host notes

- **`agents-shared`** is a location, not a product. Cline, Zed, Warp, Amp, Replit, Pi,
  Kimi Code and GitHub Copilot CLI all read `~/.agents/skills` or
  `~/.config/agents/skills`, so one sync there reaches several hosts at once. Say this
  plainly rather than implying a single application owns the directory.
- **`kiro`** is reported as not installed until `~/.kiro/skills` or
  `~/.kiro/settings/mcp.json` exists. Kiro creates `~/.kiro/steering` and
  `~/.kiro/powers` for unrelated features; neither one is a Skills directory.
- **`antigravity`** shipped two Skills locations across releases. Read the reported
  path before telling the user where a Skill landed.
- **`mimo-code`** honours `MIMOCODE_HOME`, and **`codebuddy`** honours
  `CODEBUDDY_CONFIG_DIR`. When either variable is set, the reported default is wrong;
  pass `--central` only for the central store, and tell the user their host uses a
  relocated configuration directory the script does not follow.
- **`gemini-cli`**, **`qwen-code`** and **`iflow`** keep MCP servers inside a general
  `settings.json`. Never rewrite these files wholesale; they also hold themes,
  credentials, and model selection.
- **`opencode`** and **`mimo-code`** nest servers directly under a top-level `mcp` key
  instead of `mcpServers`. Scalar options inside that block are not servers.
- **`droid`** is Factory's CLI. Both directories live under `~/.factory` on every
  platform, and `~/.factory/mcp.json` uses the `mcpServers` shape. The host reads it
  as strict JSON, so never leave a comment behind in that file. Droid also ships
  built-in Skills of its own; those are not on disk here and never appear as
  unmanaged.
- **`qoder-cn`** and **`trae-cn`** are the mainland China builds and keep separate
  directories from the international builds. Both can be installed at once.

## When a host is missing or a path looks wrong

Hosts rename directories between releases. If `status` reports `not installed` but the
user insists the host is present:

1. Ask which directory the host actually uses, or look for a plausible sibling.
2. Report the mismatch. Do not silently copy Skills into an invented path.
3. Suggest opening an issue with the product name, both platform paths, the MCP path
   and format, and whether the host accepts directory links.

## Editing MCP or other configuration

Use the script only to list MCP server names. For an edit, follow the SKILL workflow:
read the active file, show a minimal diff, create a timestamped sibling backup, change
only the named block, validate the native format, and re-read the result. Keep
comments, unrelated entries, and credentials intact.
