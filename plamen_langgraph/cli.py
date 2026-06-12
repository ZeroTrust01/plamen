from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from plamen_langgraph.plamen_lg.config import DEFAULT_SCRATCHPAD_DIR, build_config
else:
    from .plamen_lg.config import DEFAULT_SCRATCHPAD_DIR, build_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plamen-langgraph",
        description="Experimental LangGraph execution path for Plamen.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_options(command: argparse.ArgumentParser) -> None:
        command.add_argument("project_root", help="Target project path.")
        command.add_argument("--mode", default="core", choices=("light", "core", "thorough"))
        command.add_argument("--pipeline", default="sc", choices=("sc",))
        command.add_argument(
            "--language",
            default="auto",
            choices=("auto", "evm", "solana", "aptos", "sui", "soroban"),
        )
        command.add_argument(
            "--scratchpad",
            default=None,
            help=(
                "Scratchpad directory. Defaults to "
                f"<project_root>/{DEFAULT_SCRATCHPAD_DIR}."
            ),
        )
        command.add_argument(
            "--db",
            dest="db_path",
            default=None,
            help="SQLite state DB path. Defaults to <scratchpad>/plamen_lg.sqlite.",
        )
        command.add_argument("--codex-bin", default="codex")
        command.add_argument("--timeout-s", type=int, default=3000)
        command.add_argument(
            "--single-node",
            action="store_true",
            help="Run only the requested phase after predecessor validation.",
        )
        command.add_argument(
            "--base-run-id",
            default=None,
            help=(
                "Optional predecessor run id for single-node mode. Defaults to "
                "the latest successful direct predecessor in the state DB."
            ),
        )

    recon = sub.add_parser("recon", help="Run the Phase-1 recon graph.")
    add_common_options(recon)
    instantiate = sub.add_parser(
        "instantiate",
        help="Run the supported Phase-2 graph prefix: recon -> instantiate.",
    )
    add_common_options(instantiate)
    breadth = sub.add_parser(
        "breadth",
        help="Run the supported Phase-3 graph prefix: recon -> instantiate -> breadth.",
    )
    add_common_options(breadth)
    rescan = sub.add_parser(
        "rescan",
        help=(
            "Run the supported mandatory re-scan graph prefix: "
            "recon -> instantiate -> breadth -> rescan."
        ),
    )
    add_common_options(rescan)
    inventory = sub.add_parser(
        "inventory",
        help=(
            "Run the supported inventory graph prefix: "
            "recon -> instantiate -> breadth -> rescan -> inventory."
        ),
    )
    add_common_options(inventory)
    invariants = sub.add_parser(
        "invariants",
        help=(
            "Run the supported semantic invariants graph prefix: "
            "recon -> instantiate -> breadth -> rescan -> inventory -> invariants."
        ),
    )
    add_common_options(invariants)
    return parser


def _suppress_known_dependency_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"The default value of `allowed_objects` will change.*",
        category=Warning,
    )


def main(argv: list[str] | None = None) -> int:
    _suppress_known_dependency_warnings()
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = build_config(
        project_root=args.project_root,
        scratchpad=args.scratchpad,
        db_path=args.db_path,
        pipeline=args.pipeline,
        mode=args.mode,
        language=args.language,
        codex_bin=args.codex_bin,
        timeout_s=args.timeout_s,
    )
    if __package__ in (None, ""):
        from plamen_langgraph.plamen_lg.graph import run_graph, run_phase_node
    else:
        from .plamen_lg.graph import run_graph, run_phase_node

    if args.single_node:
        state = run_phase_node(
            config,
            phase_name=args.command,
            base_run_id=args.base_run_id,
        )
    else:
        state = run_graph(config, target_phase=args.command)

    print(f"run_id: {state['run_id']}")
    print(f"status: {state['status']}")
    if state.get("execution_mode") == "single_node":
        print("execution_mode: single_node")
        print(f"base_run_id: {state.get('base_run_id') or ''}")
    print(f"scratchpad: {state['scratchpad']}")
    print(f"db: {state['db_path']}")
    if state.get("error"):
        print(f"error: {state['error']}", file=sys.stderr)
    return 0 if state["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
