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


def test_breadth_cli_parses_same_options_as_recon(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratch = tmp_path / "scratch"
    db = tmp_path / "state.sqlite"

    args = _build_parser().parse_args(
        [
            "breadth",
            str(project),
            "--mode",
            "core",
            "--pipeline",
            "sc",
            "--language",
            "solana",
            "--scratchpad",
            str(scratch),
            "--db",
            str(db),
            "--codex-bin",
            "codex-test",
            "--timeout-s",
            "456",
        ]
    )

    assert args.command == "breadth"
    assert args.project_root == str(project)
    assert args.mode == "core"
    assert args.pipeline == "sc"
    assert args.language == "solana"
    assert args.scratchpad == str(scratch)
    assert args.db_path == str(db)
    assert args.codex_bin == "codex-test"
    assert args.timeout_s == 456


def test_single_node_cli_options_preserve_target_phase(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    args = _build_parser().parse_args(
        [
            "breadth",
            str(project),
            "--single-node",
            "--base-run-id",
            "run-123",
        ]
    )

    assert args.command == "breadth"
    assert args.single_node is True
    assert args.base_run_id == "run-123"
