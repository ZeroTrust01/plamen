from __future__ import annotations

from typing import Optional, TypedDict


class AuditState(TypedDict):
    run_id: str
    base_run_id: Optional[str]
    project_root: str
    scratchpad: str
    db_path: str
    pipeline: str
    mode: str
    language: str
    execution_mode: str
    current_phase: str
    target_phase: str
    completed_phases: list[str]
    failed_phase: Optional[str]
    status: str
    error: Optional[str]
