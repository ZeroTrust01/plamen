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


def test_rescan_cli_parses_same_options_as_breadth(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratch = tmp_path / "scratch"
    db = tmp_path / "state.sqlite"

    args = _build_parser().parse_args(
        [
            "rescan",
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
            "789",
        ]
    )

    assert args.command == "rescan"
    assert args.project_root == str(project)
    assert args.mode == "thorough"
    assert args.pipeline == "sc"
    assert args.language == "evm"
    assert args.scratchpad == str(scratch)
    assert args.db_path == str(db)
    assert args.codex_bin == "codex-test"
    assert args.timeout_s == 789


def test_inventory_cli_parses_same_options_as_rescan(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratch = tmp_path / "scratch"
    db = tmp_path / "state.sqlite"

    args = _build_parser().parse_args(
        [
            "inventory",
            str(project),
            "--mode",
            "core",
            "--pipeline",
            "sc",
            "--language",
            "sui",
            "--scratchpad",
            str(scratch),
            "--db",
            str(db),
            "--codex-bin",
            "codex-test",
            "--timeout-s",
            "321",
        ]
    )

    assert args.command == "inventory"
    assert args.project_root == str(project)
    assert args.mode == "core"
    assert args.pipeline == "sc"
    assert args.language == "sui"
    assert args.scratchpad == str(scratch)
    assert args.db_path == str(db)
    assert args.codex_bin == "codex-test"
    assert args.timeout_s == 321


def test_invariants_cli_parses_same_options_as_inventory(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratch = tmp_path / "scratch"
    db = tmp_path / "state.sqlite"

    args = _build_parser().parse_args(
        [
            "invariants",
            str(project),
            "--mode",
            "thorough",
            "--pipeline",
            "sc",
            "--language",
            "aptos",
            "--scratchpad",
            str(scratch),
            "--db",
            str(db),
            "--codex-bin",
            "codex-test",
            "--timeout-s",
            "654",
        ]
    )

    assert args.command == "invariants"
    assert args.project_root == str(project)
    assert args.mode == "thorough"
    assert args.pipeline == "sc"
    assert args.language == "aptos"
    assert args.scratchpad == str(scratch)
    assert args.db_path == str(db)
    assert args.codex_bin == "codex-test"
    assert args.timeout_s == 654


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


def test_single_node_cli_allows_omitted_base_run_id_for_tail_phases(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    for command in ("rescan", "inventory", "invariants"):
        args = _build_parser().parse_args(
            [
                command,
                str(project),
                "--single-node",
            ]
        )

        assert args.command == command
        assert args.single_node is True
        assert args.base_run_id is None


def test_inventory_single_node_cli_parses_base_run_id(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    args = _build_parser().parse_args(
        [
            "inventory",
            str(project),
            "--single-node",
            "--base-run-id",
            "run-123",
        ]
    )

    assert args.command == "inventory"
    assert args.single_node is True
    assert args.base_run_id == "run-123"


def test_invariants_single_node_cli_parses_base_run_id(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    args = _build_parser().parse_args(
        [
            "invariants",
            str(project),
            "--single-node",
            "--base-run-id",
            "run-123",
        ]
    )

    assert args.command == "invariants"
    assert args.single_node is True
    assert args.base_run_id == "run-123"
