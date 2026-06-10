from __future__ import annotations

from typing import Optional, TypedDict


class AuditState(TypedDict):
    run_id: str
    project_root: str
    scratchpad: str
    db_path: str
    pipeline: str
    mode: str
    language: str
    current_phase: str
    status: str
    error: Optional[str]

