import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skill" / "agent-skills-manager" / "scripts" / "asm.py"


def run_script(home: Path, *arguments: str) -> dict:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["USERPROFILE"] = str(home)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(result.stdout)


def make_skill(path: Path, content: str = "instructions") -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(content, encoding="utf-8")


def test_portable_status_reads_skills_and_mcp(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo")
    config = tmp_path / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[mcp_servers.context7]\ncommand = "npx"\n', encoding="utf-8")

    payload = run_script(tmp_path, "status", "--agent", "codex", "--json")

    assert payload["central"] == str(tmp_path / ".agent" / "skills")
    assert payload["agents"][0]["id"] == "codex"
    assert payload["agents"][0]["mcps"] == ["context7"]
    assert payload["agents"][0]["skills"][0]["status"] == "missing"


def test_portable_status_prefers_the_new_default_central(tmp_path):
    make_skill(tmp_path / ".agentskillsbank" / "skills" / "demo")

    payload = run_script(tmp_path, "status", "--agent", "codex", "--json")

    assert payload["central"] == str(tmp_path / ".agentskillsbank" / "skills")


def test_portable_sync_plans_then_applies_copy(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo", "central")
    destination = tmp_path / ".codex" / "skills" / "demo"

    plan = run_script(tmp_path, "sync", "--agent", "codex", "--mode", "copy", "--json")
    assert plan["applied"] is False
    assert not destination.exists()

    applied = run_script(
        tmp_path,
        "sync",
        "--agent",
        "codex",
        "--mode",
        "copy",
        "--json",
        "--apply",
    )
    assert applied["applied"] is True
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "central"


def test_portable_sync_plans_copy_to_link_mode_conversion(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo", "same")
    destination = tmp_path / ".codex" / "skills" / "demo"
    make_skill(destination, "same")

    plan = run_script(tmp_path, "sync", "--agent", "codex", "--mode", "link", "--json")

    assert plan["actions"][0]["skill"] == "demo"
    assert plan["actions"][0]["mode"] == "link"
    assert plan["actions"][0]["replace"] is True

    applied = run_script(
        tmp_path,
        "sync",
        "--agent",
        "codex",
        "--mode",
        "link",
        "--json",
        "--apply",
    )
    status = run_script(tmp_path, "status", "--agent", "codex", "--json")

    assert applied["applied"] is True
    assert status["agents"][0]["skills"][0]["is_link"] is True


def test_portable_import_plans_then_applies(tmp_path):
    make_skill(tmp_path / ".cursor" / "skills" / "local-only")
    destination = tmp_path / ".agentskillsbank" / "skills" / "local-only"

    plan = run_script(tmp_path, "import", "--agent", "cursor", "--json")
    assert plan["actions"][0]["skill"] == "local-only"
    assert not destination.exists()

    applied = run_script(tmp_path, "import", "--agent", "cursor", "--json", "--apply")
    assert applied["applied"] is True
    assert (destination / "SKILL.md").is_file()


def test_portable_sync_backs_up_a_different_skill(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo", "central")
    destination = tmp_path / ".codex" / "skills" / "demo"
    make_skill(destination, "local")

    applied = run_script(tmp_path, "sync", "--agent", "codex", "--json", "--apply")

    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "central"
    backup = Path(applied["backups"][0])
    assert backup.parent == tmp_path / ".agent" / "backups" / "codex"
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "local"


def test_antigravity_link_mode_falls_back_to_copy(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo")

    plan = run_script(tmp_path, "sync", "--agent", "antigravity", "--mode", "link", "--json")

    assert plan["actions"][0]["mode"] == "copy"
    assert "does not support links" in plan["warnings"][0]


def test_empty_mcp_configuration_is_treated_as_unconfigured(tmp_path):
    config = tmp_path / ".gemini" / "antigravity" / "mcp_config.json"
    config.parent.mkdir(parents=True)
    config.write_text("", encoding="utf-8")

    payload = run_script(tmp_path, "status", "--agent", "antigravity", "--json")

    assert payload["agents"][0]["skills_path"] == str(tmp_path / ".gemini" / "config" / "skills")
    assert payload["agents"][0]["mcps"] == []
    assert payload["agents"][0]["errors"] == []


def test_portable_status_counts_missing_without_demanding_attention(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "installed")
    make_skill(tmp_path / ".agent" / "skills" / "not-installed")
    make_skill(tmp_path / ".codex" / "skills" / "installed")

    payload = run_script(tmp_path, "status", "--agent", "codex", "--json")

    assert payload["agents"][0]["present"] == 1
    assert payload["agents"][0]["missing"] == 1
    assert payload["agents"][0]["attention"] is False


def test_portable_status_flags_an_unmanaged_skill(tmp_path):
    make_skill(tmp_path / ".codex" / "skills" / "agent-only")

    payload = run_script(tmp_path, "status", "--agent", "codex", "--json")

    assert payload["agents"][0]["attention"] is True


def test_portable_status_compares_contents_only_when_verifying(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo", "central")
    make_skill(tmp_path / ".codex" / "skills" / "demo", "local")

    fast = run_script(tmp_path, "status", "--agent", "codex", "--json")
    verified = run_script(tmp_path, "status", "--agent", "codex", "--verify", "--json")

    assert fast["verified"] is False
    assert fast["agents"][0]["skills"][0]["status"] == "ready"
    assert verified["verified"] is True
    assert verified["agents"][0]["skills"][0]["status"] == "different"


def test_portable_sync_still_detects_a_changed_skill_without_status_verification(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo", "central")
    make_skill(tmp_path / ".codex" / "skills" / "demo", "local")

    plan = run_script(tmp_path, "sync", "--agent", "codex", "--json")

    assert plan["actions"][0]["skill"] == "demo"
    assert plan["actions"][0]["replace"] is True


def test_portable_script_manages_a_newly_supported_agent(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "demo", "central")
    config = tmp_path / ".qoder" / "mcp.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"mcpServers": {"context7": {"command": "npx"}}}', encoding="utf-8")

    applied = run_script(tmp_path, "sync", "--agent", "qoder", "--json", "--apply")
    payload = run_script(tmp_path, "status", "--agent", "qoder", "--json")

    assert applied["applied"] is True
    assert (tmp_path / ".qoder" / "skills" / "demo" / "SKILL.md").is_file()
    assert payload["agents"][0]["mcps"] == ["context7"]


def test_portable_script_reads_an_opencode_style_mcp_block(tmp_path):
    config = tmp_path / ".config" / "opencode" / "opencode.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"mcp": {"github": {"type": "local"}}}', encoding="utf-8")

    payload = run_script(tmp_path, "status", "--agent", "opencode", "--json")

    assert payload["agents"][0]["mcps"] == ["github"]


def test_portable_script_picks_the_mcp_candidate_that_exists(tmp_path):
    legacy = tmp_path / ".codebuddy" / "mcp.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"mcpServers": {"legacy": {}}}', encoding="utf-8")

    payload = run_script(tmp_path, "status", "--agent", "codebuddy", "--json")

    assert payload["agents"][0]["mcp_path"] == str(legacy)
    assert payload["agents"][0]["mcps"] == ["legacy"]


def test_non_skill_directories_are_ignored(tmp_path):
    make_skill(tmp_path / ".codex" / "skills" / "real-skill")
    make_skill(tmp_path / ".codex" / "skills" / ".system")

    payload = run_script(tmp_path, "status", "--agent", "codex", "--json")

    assert [item["name"] for item in payload["agents"][0]["skills"]] == ["real-skill"]


def test_portable_diff_reports_skill_and_file_differences(tmp_path):
    central = tmp_path / ".agent" / "skills"
    agent = tmp_path / ".codex" / "skills"
    make_skill(central / "same", "same")
    make_skill(agent / "same", "same")
    make_skill(central / "changed", "central")
    make_skill(agent / "changed", "agent")
    (central / "changed" / "central-only.txt").write_text("central", encoding="utf-8")
    (agent / "changed" / "agent-only.txt").write_text("agent", encoding="utf-8")
    make_skill(central / "missing")
    make_skill(agent / "extra")

    payload = run_script(tmp_path, "diff", "--agent", "codex", "--json")

    result = payload["agents"][0]
    assert result["summary"] == {
        "identical": 1,
        "missing": 1,
        "extra": 1,
        "different": 1,
    }
    assert [item["name"] for item in result["skills"]] == ["changed", "extra", "missing"]
    changed = result["skills"][0]
    assert changed["status"] == "different"
    assert changed["files"] == [
        {"path": "agent-only.txt", "status": "only-agent"},
        {"path": "central-only.txt", "status": "only-central"},
        {"path": "SKILL.md", "status": "modified"},
    ]


def test_portable_diff_can_filter_skills_and_include_identical(tmp_path):
    make_skill(tmp_path / ".agent" / "skills" / "same", "same")
    make_skill(tmp_path / ".codex" / "skills" / "same", "same")
    make_skill(tmp_path / ".agent" / "skills" / "ignored", "central")

    payload = run_script(
        tmp_path,
        "diff",
        "--agent",
        "codex",
        "--skill",
        "same",
        "--all",
        "--json",
    )

    assert payload["agents"][0]["summary"]["identical"] == 1
    assert payload["agents"][0]["skills"][0]["status"] == "identical"
