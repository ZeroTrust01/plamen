from __future__ import annotations

from plamen_langgraph.plamen_lg.runner import CodexRunner


def test_runner_uses_workspace_write_sandbox(tmp_path):
    runner = CodexRunner("codex")
    cmd = runner.build_command(
        project_root=tmp_path,
        prompt="recon",
        last_message_path=tmp_path / "last.md",
    )

    assert "--sandbox" in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"

