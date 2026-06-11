from __future__ import annotations

from plamen_langgraph.cli import _build_parser


def test_instantiate_cli_parses_same_options_as_recon(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratch = tmp_path / "scratch"
    db = tmp_path / "state.sqlite"

    args = _build_parser().parse_args(
        [
            "instantiate",
            str(project),
            "--mode",
            "thorough",
            "--pipeline",
            "sc",
            "--language",
            "evm",
            "--scratchpad",
            str(scratch),
            "--db",
            str(db),
            "--codex-bin",
            "codex-test",
            "--timeout-s",
            "123",
        ]
    )

    assert args.command == "instantiate"
    assert args.project_root == str(project)
    assert args.mode == "thorough"
    assert args.pipeline == "sc"
    assert args.language == "evm"
    assert args.scratchpad == str(scratch)
    assert args.db_path == str(db)
    assert args.codex_bin == "codex-test"
    assert args.timeout_s == 123
