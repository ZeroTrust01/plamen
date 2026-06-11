from __future__ import annotations

import sqlite3

from plamen_langgraph.plamen_lg.store import StateStore


def test_sqlite_schema_initializes(tmp_path):
    db = tmp_path / "plamen_lg.sqlite"
    store = StateStore(db)
    store.init_db()

    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }

    assert {"runs", "phase_runs", "artifacts"} <= tables


def test_run_and_phase_rows_can_be_created_and_updated(tmp_path):
    store = StateStore(tmp_path / "plamen_lg.sqlite")
    store.init_db()
    store.create_run("run-1", "/repo", "/repo/.lg_scratchpad", "recon")
    store.update_run_status("run-1", "running")
    store.create_phase_run("phase-1", "run-1", "recon")
    store.update_phase_run(
        "phase-1",
        "succeeded",
        returncode=0,
        stdout_path="stdout.log",
        stderr_path="stderr.log",
        events_path="events.jsonl",
        output_path="last.md",
    )

    run = store.fetch_one("select status from runs where id = ?", ("run-1",))
    phase = store.fetch_one(
        "select status, returncode, stdout_path from phase_runs where id = ?",
        ("phase-1",),
    )

    assert run == {"status": "running"}
    assert phase == {"status": "succeeded", "returncode": 0, "stdout_path": "stdout.log"}
