from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RECON_ARTIFACTS = [
    "recon_summary.md",
    "design_context.md",
    "attack_surface.md",
    "state_variables.md",
    "function_list.md",
    "contract_inventory.md",
    "template_recommendations.md",
    "detected_patterns.md",
    "setter_list.md",
    "emit_list.md",
    "build_status.md",
]


@dataclass(frozen=True)
class SimplePhase:
    name: str
    section_markers: list[str]
    expected_artifacts: list[str]
    base_timeout_s: int
    critical: bool = True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_legacy_scripts_on_path() -> None:
    scripts = _repo_root() / "scripts"
    if scripts.exists() and str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))


def get_recon_phase(pipeline: str = "sc") -> Any:
    if pipeline != "sc":
        raise ValueError("Phase 1 supports only SC recon")
    _ensure_legacy_scripts_on_path()
    try:
        from plamen_types import SC_PHASES

        return next(phase for phase in SC_PHASES if phase.name == "recon")
    except Exception:
        return SimplePhase(
            name="recon",
            section_markers=[
                "Step 1: Language Detection",
                "Step 1.5: Scratchpad",
                "Phase 1: Reconnaissance",
            ],
            expected_artifacts=list(RECON_ARTIFACTS),
            base_timeout_s=3000,
            critical=True,
        )


def resolve_v1_prompt(pipeline: str = "sc") -> Path:
    _ensure_legacy_scripts_on_path()
    from plamen_prompt import resolve_v1_prompt as _resolve_v1_prompt

    return _resolve_v1_prompt(pipeline)


def build_recon_prompt(config: dict[str, Any]) -> str:
    """Build the recon prompt using the legacy prompt builder."""
    _ensure_legacy_scripts_on_path()
    try:
        from plamen_prompt import build_phase_prompt

        phase = get_recon_phase(str(config.get("pipeline", "sc")))
        return build_phase_prompt(resolve_v1_prompt(str(config.get("pipeline", "sc"))), phase, config)
    except Exception as exc:
        return build_minimal_recon_prompt(config, exc)


def build_minimal_recon_prompt(config: dict[str, Any], cause: Exception | None = None) -> str:
    required = "\n".join(f"- `{name}`" for name in RECON_ARTIFACTS)
    cause_text = f"\nLegacy prompt builder unavailable: `{cause}`.\n" if cause else ""
    return f"""# Plamen LangGraph Phase 1 Recon

Phase 1 temporary prompt is acceptable only as a bridge.
Phase 2 should reuse the production prompt builder.
{cause_text}
You are running only the `recon` phase for Plamen's smart-contract audit
pipeline. Do not run breadth, inventory, depth, verification, or report phases.

Project root: `{config.get('project_root')}`
Scratchpad: `{config.get('scratchpad')}`
Mode: `{config.get('mode')}`
Pipeline: `{config.get('pipeline')}`
Language: `{config.get('language')}`

Write these required recon artifacts directly under the scratchpad:

{required}

Each artifact must contain substantive best-known content. If a detail is not
available after bounded inspection, write `UNAVAILABLE` with the reason. Do not
leave TODO, TBD, placeholder tokens, or draft-only markers.

Return after these exact recon artifacts are written.
"""


def expected_recon_artifacts() -> list[str]:
    return list(get_recon_phase("sc").expected_artifacts)
