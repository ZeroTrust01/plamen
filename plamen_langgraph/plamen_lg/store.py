from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
create table if not exists runs (
  id text primary key,
  project_root text not null,
  scratchpad text not null,
  phase text not null,
  status text not null,
  created_at text not null,
  updated_at text not null
);

create table if not exists phase_runs (
  id text primary key,
  run_id text not null,
  phase_name text not null,
  status text not null,
  returncode integer,
  stdout_path text,
  stderr_path text,
  events_path text,
  output_path text,
  started_at text,
  finished_at text,
  error text,
  foreign key(run_id) references runs(id)
);

create table if not exists artifacts (
  id text primary key,
  run_id text not null,
  phase_name text not null,
  path text not null,
  "exists" integer not null,
  size_bytes integer,
  sha256 text,
  created_at text not null,
  foreign key(run_id) references runs(id)
);
"""


class StateStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def create_run(
        self,
        run_id: str,
        project_root: str,
        scratchpad: str,
        phase: str,
        status: str = "pending",
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                insert into runs (id, project_root, scratchpad, phase, status, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, project_root, scratchpad, phase, status, now, now),
            )

    def update_run_status(self, run_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "update runs set status = ?, updated_at = ? where id = ?",
                (status, utc_now(), run_id),
            )

    def create_phase_run(
        self,
        phase_run_id: str,
        run_id: str,
        phase_name: str,
        status: str = "running",
        started_at: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into phase_runs
                  (id, run_id, phase_name, status, started_at)
                values (?, ?, ?, ?, ?)
                """,
                (phase_run_id, run_id, phase_name, status, started_at or utc_now()),
            )

    def update_phase_run(
        self,
        phase_run_id: str,
        status: str,
        returncode: int | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        events_path: str | None = None,
        output_path: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                update phase_runs
                set status = ?,
                    returncode = ?,
                    stdout_path = ?,
                    stderr_path = ?,
                    events_path = ?,
                    output_path = ?,
                    started_at = coalesce(?, started_at),
                    finished_at = ?,
                    error = ?
                where id = ?
                """,
                (
                    status,
                    returncode,
                    stdout_path,
                    stderr_path,
                    events_path,
                    output_path,
                    started_at,
                    finished_at or utc_now(),
                    error,
                    phase_run_id,
                ),
            )

    def record_artifact(
        self,
        run_id: str,
        phase_name: str,
        path: str,
        exists: bool,
        size_bytes: int | None,
        sha256: str | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into artifacts
                  (id, run_id, phase_name, path, "exists", size_bytes, sha256, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    run_id,
                    phase_name,
                    path,
                    1 if exists else 0,
                    size_bytes,
                    sha256,
                    utc_now(),
                ),
            )

    def record_artifacts(self, run_id: str, phase_name: str, records: list[dict[str, Any]]) -> None:
        for record in records:
            self.record_artifact(
                run_id,
                phase_name,
                str(record["path"]),
                bool(record["exists"]),
                record.get("size_bytes"),
                record.get("sha256"),
            )

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
