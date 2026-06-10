from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plamen_langgraph.plamen_lg.config import build_config
from plamen_langgraph.plamen_lg.graph import run_recon_graph


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python plamen_langgraph/examples/run_recon.py /path/to/project")
        return 2
    state = run_recon_graph(build_config(sys.argv[1]))
    print(state)
    return 0 if state["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())

