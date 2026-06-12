"""Internal implementation for the Plamen LangGraph runner."""

from .config import AuditConfig, build_config

__all__ = [
    "AuditConfig",
    "build_config",
    "build_graph",
    "run_recon_graph",
    "run_inventory_graph",
    "run_depth_graph",
]


def __getattr__(name: str):
    if name in {
        "build_graph",
        "run_recon_graph",
        "run_inventory_graph",
        "run_depth_graph",
    }:
        from .graph import (
            build_graph,
            run_depth_graph,
            run_inventory_graph,
            run_recon_graph,
        )

        return {
            "build_graph": build_graph,
            "run_recon_graph": run_recon_graph,
            "run_inventory_graph": run_inventory_graph,
            "run_depth_graph": run_depth_graph,
        }[name]
    raise AttributeError(name)
