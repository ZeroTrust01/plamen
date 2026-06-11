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

    recon = sub.add_parser("recon", help="Run the Phase-1 recon graph.")
    recon.add_argument("project_root", help="Target project path.")
    recon.add_argument("--mode", default="core", choices=("light", "core", "thorough"))
    recon.add_argument("--pipeline", default="sc", choices=("sc",))
    recon.add_argument(
        "--language",
        default="auto",
        choices=("auto", "evm", "solana", "aptos", "sui", "soroban"),
    )
    recon.add_argument(
        "--scratchpad",
        default=None,
        help=(
            "Scratchpad directory. Defaults to "
            f"<project_root>/{DEFAULT_SCRATCHPAD_DIR}."
        ),
    )
    recon.add_argument(
        "--db",
        dest="db_path",
        default=None,
        help="SQLite state DB path. Defaults to <scratchpad>/plamen_lg.sqlite.",
    )
    recon.add_argument("--codex-bin", default="codex")
    recon.add_argument("--timeout-s", type=int, default=3000)
    return parser


def _suppress_known_dependency_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"The default value of `allowed_objects` will change.*",
        category=Warning,
    )


def main(argv: list[str] | None = None) -> int:
    _suppress_known_dependency_warnings()
    args = _build_parser().parse_args(argv)
    if args.command != "recon":
        raise SystemExit(f"unsupported command: {args.command}")

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
        from plamen_langgraph.plamen_lg.graph import run_recon_graph
    else:
        from .plamen_lg.graph import run_recon_graph

    state = run_recon_graph(config)

    print(f"run_id: {state['run_id']}")
    print(f"status: {state['status']}")
    print(f"scratchpad: {state['scratchpad']}")
    print(f"db: {state['db_path']}")
    if state.get("error"):
        print(f"error: {state['error']}", file=sys.stderr)
    return 0 if state["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
