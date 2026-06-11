# Plamen LangGraph Phase 1-2 Refactor Plan

## Objective

Build a new LangGraph-based execution path for Plamen without mixing it into the existing driver implementation.

Phase 1 intentionally supports only one phase: `recon`.
Phase 2 extends the same execution path to the second canonical smart-contract phase: `instantiate`.

The Phase 1 goal is to prove the new architecture can:

- create a run
- execute one Codex CLI worker through LangGraph
- write artifacts into the target project's LangGraph scratchpad
- record run, phase, and artifact status in SQLite
- leave the existing `plamen` CLI and `scripts/plamen_driver.py` behavior unchanged

The Phase 2 goal is to prove that the architecture can:

- execute a two-node phase graph: `recon -> instantiate`
- preserve phase ordering and stop after a failed upstream phase
- write and validate `spawn_manifest.md`
- record multiple `phase_runs` rows for one run
- keep the legacy driver and legacy checkpoint behavior untouched

## High-Level Architecture

```text
new CLI entry
  -> LangGraph graph
      -> recon phase node
          -> CodexRunner
              -> codex exec -C <repo> <prompt>
          -> artifact checker
          -> SQLite state store
      -> end
```

Phase 2 target shape:

```text
new CLI entry
  -> LangGraph graph
      -> recon phase node
          -> CodexRunner
          -> recon artifact checker
          -> SQLite state store
      -> instantiate phase node
          -> CodexRunner
          -> spawn_manifest schema gate
          -> SQLite state store
      -> end
```

Long-term target architecture:

```text
LangGraph = phase orchestrator
Codex CLI = code/audit worker
SQLite = durable state and artifact index
Scratchpad = markdown artifact storage
Web UI = state and artifact viewer
Worktree/container = execution isolation
```

Phase 1 only implements the first vertical slice for `recon`.
Phase 2 implements the next canonical SC phase without adding breadth workers yet.

## Directory Strategy

All new code goes under a new top-level directory:

```text
plamen_langgraph/
  README.md
  requirements.txt

  plamen_lg/
    __init__.py
    config.py
    state.py
    graph.py
    runner.py
    store.py
    phases.py
    artifacts.py

  cli.py

  examples/
    run_recon.py
```

This prevents confusion with the existing implementation:

- Do not put LangGraph code in `scripts/`.
- Do not modify `scripts/plamen_driver.py` for Phase 1 or Phase 2.
- Do not change the default behavior of `plamen.py`.
- Do not replace existing checkpoint logic in Phase 1 or Phase 2.

## Existing Assets To Reuse

The new implementation should reuse existing Plamen assets as read-only dependencies where practical.

Useful existing files:

- `scripts/plamen_types.py`
  - Source of canonical phase definitions.
  - Phase 1 needs the `recon` phase definition from `SC_PHASES`.
  - Phase 2 needs the `instantiate` phase definition from `SC_PHASES`.

- `scripts/plamen_prompt.py`
  - Source of existing phase prompt construction logic.
  - Prefer reuse over creating divergent prompt formats.
  - Phase 2 should reuse `prompts/shared/v2/phase2-instantiate.md` as the methodology body with a LangGraph direct-execution wrapper.

- `scripts/plamen_validators.py`
  - Source of artifact gate and validation logic.
  - Phase 1 can start with a simple file-existence check and then wire in stricter validators.
  - Phase 2 should reuse `_validate_spawn_manifest_schema()` or an equivalent local wrapper that uses the same parser contract.

- `scripts/plamen_parsers.py`
  - Later useful for extracting structured findings and report inputs.
  - Not required for the first `recon` slice unless needed by prompt or validation reuse.

- `scripts/plamen_mechanical.py`
  - Useful later for deterministic report assembly.
  - Out of scope for Phase 1 and Phase 2.

## Phase 1 Scope

Implement only:

```text
recon
```

Phase 1 must not implement:

- full SC phase graph
- L1 phase graph
- breadth/depth/verification/report phases
- dynamic verification shards
- dynamic report shards
- parallel Codex workers
- web UI
- full audit resume
- replacement of the legacy driver
- automatic integration into the existing `plamen core ...` command

## New CLI

Add a new entry point independent of the legacy CLI:

```bash
python -m plamen_langgraph.cli recon /path/to/project
```

Phase 2 should add a second command that runs the supported SC prefix through
`instantiate`:

```bash
python -m plamen_langgraph.cli instantiate /path/to/project
```

The `instantiate` command must execute both supported nodes:

```text
recon -> instantiate
```

It must not skip `recon` implicitly. A later resume design can reuse existing
recon artifacts, but Phase 2 keeps execution simple and deterministic.

Fallback direct execution may also be supported:

```bash
python plamen_langgraph/cli.py recon /path/to/project
python plamen_langgraph/cli.py instantiate /path/to/project
```

Initial options:

```bash
python -m plamen_langgraph.cli recon /path/to/project \
  --mode core \
  --pipeline sc \
  --language auto \
  --db /path/to/project/.lg_scratchpad/plamen_lg.sqlite
```

Defaults:

- `mode`: `core`
- `pipeline`: `sc`
- `language`: auto-detected if possible
- `scratchpad`: `<project>/.lg_scratchpad`
- `db`: `<project>/.lg_scratchpad/plamen_lg.sqlite`

Phase 2 CLI implementation tasks:

1. Keep the existing `recon` command behavior unchanged.
2. Add `instantiate` with the same options as `recon`.
3. Route `recon` to a graph with `target_phase = "recon"`.
4. Route `instantiate` to a graph with `target_phase = "instantiate"`.
5. Print the same run summary fields: `run_id`, `status`, `scratchpad`, and `db`.
6. Return exit code `0` only when the requested target phase succeeds.

## Codex Runner

Create `plamen_langgraph/plamen_lg/runner.py`.

Responsibilities:

- build a safe Codex CLI command
- run Codex non-interactively
- capture stdout and stderr
- save JSONL event stream when `--json` is enabled
- save the final assistant message with `--output-last-message`
- enforce timeout
- return a structured result

Recommended command shape:

```bash
codex exec \
  -C /path/to/project \
  --json \
  --output-last-message /path/to/project/.lg_scratchpad/recon_last_message.md \
  "<prompt>"
```

Runner result shape:

```python
{
    "stdout_path": "...",
    "stderr_path": "...",
    "events_path": "...",
    "last_message_path": "...",
    "returncode": 0,
    "started_at": "...",
    "finished_at": "...",
    "duration_s": 123.4,
}
```

Security rules:

- Do not use `--dangerously-bypass-approvals-and-sandbox` by default.
- If dangerous mode is later added, require an isolated container or disposable worktree.
- Do not run multiple Codex workers against the same writable repository in Phase 1 or Phase 2.
- Phase 2 still runs workers sequentially.

## LangGraph State

Create `plamen_langgraph/plamen_lg/state.py`.

Initial state type:

```python
from typing import TypedDict, Optional

class AuditState(TypedDict):
    run_id: str
    project_root: str
    scratchpad: str
    db_path: str
    pipeline: str
    mode: str
    language: str
    current_phase: str
    target_phase: str
    completed_phases: list[str]
    failed_phase: Optional[str]
    status: str
    error: Optional[str]
```

Phase 1 does not need a complex routing state. It only needs to run:

```text
START -> recon -> END
```

Phase 2 can keep routing deterministic:

```text
target_phase = "recon":       START -> recon -> END
target_phase = "instantiate": START -> recon -> instantiate -> END
```

Do not add dynamic branching for later phases in Phase 2. The only conditional
behavior should be that `instantiate` returns immediately with failed state if
`recon` did not succeed.

## LangGraph Graph

Create `plamen_langgraph/plamen_lg/graph.py`.

Graph shape:

```text
START
  -> recon
  -> END
```

Phase 2 graph shape:

```text
START
  -> recon
  -> instantiate
  -> END
```

The implementation can use one graph builder with a `target_phase` argument or
two small wrappers:

```python
run_recon_graph(config, runner=None)
run_instantiate_graph(config, runner=None)
```

Preferred internal API:

```python
run_graph(config, target_phase="recon", runner=None)
```

Then keep `run_recon_graph()` as a compatibility wrapper for existing tests.

The `recon` node should:

1. Load or construct the `recon` phase definition.
2. Build the recon prompt.
3. Insert a `phase_runs` row with status `running`.
4. Call `CodexRunner`.
5. Check expected artifacts.
6. Update `phase_runs` status to `succeeded` or `failed`.
7. Update the parent `runs` row.
8. Return updated state.

The `instantiate` node should:

1. Check that `state["status"] == "succeeded"` and `recon` is in `completed_phases`.
2. Load or construct the `instantiate` phase definition.
3. Build a Phase 2 direct-execution prompt.
4. Write the prompt snapshot to `_lg_instantiate_prompt.md`.
5. Insert a `phase_runs` row with status `running`.
6. Call `CodexRunner`.
7. Check that `spawn_manifest.md` exists and is substantial.
8. Validate `spawn_manifest.md` with the legacy-compatible schema gate.
9. Record the artifact row for `spawn_manifest.md`.
10. Update `phase_runs` and parent `runs` to `succeeded`, `failed`, or `timeout`.
11. Append `instantiate` to `completed_phases` only on success.
12. Return updated state.

## Prompt Strategy

Phase 1 preferred approach:

1. Reuse existing `scripts/plamen_prompt.py` to build a recon phase prompt.
2. Use the existing `SC_PHASES` `recon` definition from `scripts/plamen_types.py`.
3. Write the prompt snapshot to `.lg_scratchpad/_lg_recon_prompt.md` for debugging.

If existing prompt construction is too tightly coupled to the legacy driver, use a temporary minimal recon prompt for Phase 1, but keep the compatibility target explicit:

```text
Phase 1 temporary prompt is acceptable only as a bridge.
Phase 2 should reuse production Phase 2 methodology content.
```

Phase 2 prompt requirements:

1. Add `build_instantiate_prompt(config)` in `plamen_langgraph/plamen_lg/phases.py`.
2. Load `prompts/shared/v2/phase2-instantiate.md` from the Plamen installation root.
3. Wrap that methodology in a LangGraph direct-execution prompt that provides:
   - project root
   - scratchpad
   - pipeline
   - mode
   - language
   - required recon input artifacts
   - required output artifact: `spawn_manifest.md`
4. Explicitly scope the worker to Phase 2 only:
   - read recon artifacts
   - write only `spawn_manifest.md` and optional debug notes with `_lg_` prefix
   - do not run breadth, inventory, depth, verification, scoring, or report work
   - do not spawn subagents from inside the Phase 2 worker
5. Include the machine-readable table contract from `phase2-instantiate.md`.
6. Write `_lg_instantiate_prompt.md` before calling Codex.

The Phase 2 direct-execution wrapper should not invoke the legacy orchestrator
prompt wholesale if doing so leaks future phase control flow or `Task(...)`
subagent directives. Reusing the standalone shared V2 prompt body is the
compatibility target.

## Artifact Contract

For Phase 1, expect the same basic recon artifacts as the legacy `recon` phase:

```text
recon_summary.md
design_context.md
attack_surface.md
state_variables.md
function_list.md
contract_inventory.md
template_recommendations.md
detected_patterns.md
setter_list.md
emit_list.md
build_status.md
```

Artifact checker behavior:

- Check each expected artifact under the configured LangGraph scratchpad.
- Record each artifact in SQLite with existence and size.
- Mark the phase failed if required artifacts are missing.
- Do not write or mutate legacy `_v2_checkpoint.json` in Phase 1.

Create `plamen_langgraph/plamen_lg/artifacts.py`.

Initial result shape:

```python
{
    "ok": True,
    "missing": [],
    "present": [
        {
            "path": "...",
            "size_bytes": 1234,
            "sha256": "...",
        }
    ],
}
```

Phase 2 artifact contract:

```text
spawn_manifest.md
```

`spawn_manifest.md` must follow the producer-side schema already enforced by
`scripts/plamen_validators.py::_validate_spawn_manifest_schema()`:

- file exists under the configured LangGraph scratchpad
- file size is at least 50 bytes
- first parseable breadth-agent table includes `Template` and `Required?` columns
- every spawned `AGENT` row has a unique agent identifier
- every spawned `AGENT` row maps to a distinct first-pass `analysis_*.md` output
- no spawned row points at `verify_*.md`, `analysis_rescan_*.md`,
  `analysis_percontract_*.md`, `analysis_merged_into_*.md`, inventory, depth,
  chain, verification, or report artifacts

Implementation tasks:

1. Keep `check_artifacts()` for generic existence/size/hash recording.
2. Add a phase-specific validator hook:

   ```python
   validate_phase_artifacts(phase_name, scratchpad, records) -> list[str]
   ```

3. For `recon`, the validator can return `[]` after the existing file checks.
4. For `instantiate`, call the spawn manifest schema gate after the generic file check.
5. If importing `_validate_spawn_manifest_schema()` pulls in too much legacy state,
   add a local compatibility validator and tests that assert the same accepted and
   rejected examples.

## SQLite Store

Create `plamen_langgraph/plamen_lg/store.py`.

Phase 1 schema:

```sql
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
  exists integer not null,
  size_bytes integer,
  sha256 text,
  created_at text not null,
  foreign key(run_id) references runs(id)
);
```

Phase 2 does not need a schema migration. It should reuse the existing tables:

- one row in `runs`
- one `phase_runs` row for `recon`
- one `phase_runs` row for `instantiate`
- artifact rows with `phase_name = "recon"` for recon outputs
- artifact row with `phase_name = "instantiate"` for `spawn_manifest.md`

For Phase 2, the `runs.phase` column should store the requested target phase:

```text
recon        # `python -m plamen_langgraph.cli recon ...`
instantiate  # `python -m plamen_langgraph.cli instantiate ...`
```

Do not add resume tables, checkpoint tables, worker tables, or worktree tables in
Phase 2.

State transitions:

```text
runs.status:
  pending -> running -> succeeded
                     -> failed

phase_runs.status:
  pending -> running -> succeeded
                         failed
                         timeout
```

## Configuration

Create `plamen_langgraph/plamen_lg/config.py`.

Initial config fields:

```python
{
    "project_root": "...",
    "scratchpad": "...",
    "db_path": "...",
    "pipeline": "sc",
    "mode": "core",
    "language": "evm|solana|aptos|sui|soroban|auto",
    "codex_bin": "codex",
    "timeout_s": 3000,
}
```

For Phase 1, config can be built directly from CLI args. It does not need to be compatible with every legacy `config.json` field.

For Phase 2, keep the same config fields. Do not add broad legacy config
compatibility yet.

## Isolation Rules

Phase 1 uses the target repository directly, but documents the future isolation model.

Rules for Phase 1 and Phase 2:

- One run at a time per project.
- No parallel Codex subprocesses.
- Do not pass dangerous Codex sandbox bypass flags.
- Write only to the configured LangGraph scratchpad unless Codex itself creates normal build cache files as part of bounded inspection.
- Do not write or mutate legacy `.scratchpad/_v2_checkpoint.json`.

Future isolation:

- one git worktree per worker
- or one container per worker
- SQLite records the worktree/container ID
- artifacts are copied back to the canonical scratchpad

## Logging And Debug Files

For a run with ID `<run_id>`, write:

```text
.lg_scratchpad/
  plamen_lg.sqlite
  _lg_recon_prompt.md
  _lg_recon_stdout.log
  _lg_recon_stderr.log
  _lg_recon_events.jsonl
  _lg_recon_last_message.md
  _lg_instantiate_prompt.md
  _lg_instantiate_stdout.log
  _lg_instantiate_stderr.log
  _lg_instantiate_events.jsonl
  _lg_instantiate_last_message.md
```

These files are separate from legacy driver files and should not collide with `_v2_checkpoint.json` or `_plamen.log`.

## Tests

Add tests under:

```text
plamen_langgraph/tests/
```

Phase 1 test targets:

- SQLite schema initializes.
- A run row can be created and updated.
- A phase row can be created and updated.
- Artifact checker detects present and missing files.
- Graph can run with a mocked `CodexRunner`.
- Mocked successful recon marks run as `succeeded`.
- Mocked missing artifacts marks run as `failed`.
- Legacy files such as `_v2_checkpoint.json` are not created or modified.

Phase 2 test targets:

- `get_phase("instantiate")` returns the canonical SC second phase metadata.
- `build_instantiate_prompt()` includes the Phase 2 methodology body and excludes `Task(subagent_type=...)`.
- `python -m plamen_langgraph.cli instantiate ...` parses the same options as `recon`.
- Mocked `run_graph(target_phase="instantiate")` calls the runner twice in order: `recon`, then `instantiate`.
- If mocked recon fails, instantiate is not called and no `phase_runs` row for `instantiate` is created.
- Mocked successful instantiate writes `spawn_manifest.md`, records two phase rows, and marks the run `succeeded`.
- Missing `spawn_manifest.md` marks `instantiate` and the parent run `failed`.
- Invalid `spawn_manifest.md` schema marks `instantiate` and the parent run `failed`.
- `spawn_manifest.md` artifact row is recorded with `phase_name = "instantiate"`.
- Existing `run_recon_graph()` tests continue to pass unchanged.
- Legacy files such as `_v2_checkpoint.json` are still not created or modified.

Do not require a real Codex CLI call in unit tests. Real Codex invocation can be covered by a manual smoke test.

## Manual Smoke Test

Use a small local repository as target:

```bash
python -m plamen_langgraph.cli recon /path/to/small/project
```

Phase 2 smoke command:

```bash
python -m plamen_langgraph.cli instantiate /path/to/small/project
```

Then verify:

```bash
ls -la /path/to/small/project/.lg_scratchpad
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite ".tables"
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite "select phase, status from runs;"
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite "select phase_name, status, returncode from phase_runs order by started_at;"
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite "select phase_name, path, exists from artifacts order by created_at;"
```

Expected result:

- `runs.status = succeeded` if all required recon artifacts exist.
- `phase_runs.status = succeeded`.
- required recon artifacts exist under `.lg_scratchpad`.
- Phase 2 only: `spawn_manifest.md` exists under `.lg_scratchpad`.
- Phase 2 only: `phase_runs` contains exactly one `recon` row and one `instantiate` row.
- no legacy full-pipeline checkpoint is written by the new implementation.

## Acceptance Criteria

Phase 1 is complete when:

1. All new implementation files live under `plamen_langgraph/`.
2. Existing `plamen.py` and `scripts/plamen_driver.py` behavior is unchanged.
3. `python -m plamen_langgraph.cli recon /path/to/project` runs a LangGraph graph.
4. The graph executes exactly one phase: `recon`.
5. Codex CLI is invoked through a dedicated runner wrapper.
6. stdout, stderr, JSONL events, prompt snapshot, and final message are saved under `.lg_scratchpad`.
7. SQLite records run, phase, and artifact status.
8. Recon artifacts are checked and recorded.
9. Unit tests pass with a mocked Codex runner.
10. A manual smoke test can run against a small repo.

## Phase 2 Implementation Plan

Phase 2 should implement the actual second smart-contract phase from
`SC_PHASES`:

```text
recon -> instantiate
```

Rationale:

- `instantiate` is the canonical second phase in `scripts/plamen_types.py`.
- It consumes recon artifacts and produces the breadth spawn contract.
- It validates multi-node graph routing without adding parallel workers.
- It exercises a stricter phase-specific validator through `spawn_manifest.md`.

Do not implement `inventory_prepare` in Phase 2. In the legacy SC graph it is a
later Phase 4a mechanical step after breadth/rescan, not the second phase.

Phase 2 development checklist:

1. Add generic phase helpers in `plamen_langgraph/plamen_lg/phases.py`:
   - `get_phase(name, pipeline="sc")`
   - `expected_phase_artifacts(name)`
   - `build_phase_prompt(name, config)`
   - keep `get_recon_phase()` and `build_recon_prompt()` as wrappers if tests use them
2. Add `build_instantiate_prompt(config)` using `prompts/shared/v2/phase2-instantiate.md`.
3. Generalize graph output paths from recon-only names to `_lg_<phase>_*`.
4. Add an `instantiate` node with the behavior described above.
5. Add `run_graph(config, target_phase)` and keep `run_recon_graph()` as a wrapper.
6. Add `run_instantiate_graph()` or route the CLI command directly to `run_graph(..., "instantiate")`.
7. Add phase-specific artifact validation for `spawn_manifest.md`.
8. Update the README to document the new command and files.
9. Add unit tests before manual smoke testing.
10. Run the existing Phase 1 tests to prove recon behavior did not regress.

Phase 2 acceptance criteria:

1. `python -m plamen_langgraph.cli recon /path/to/project` still runs only `recon`.
2. `python -m plamen_langgraph.cli instantiate /path/to/project` runs `recon -> instantiate`.
3. If `recon` fails, `instantiate` is not executed.
4. `spawn_manifest.md` is required, substantial, schema-valid, and recorded in SQLite.
5. The run has two successful `phase_runs` rows when both phases pass.
6. No breadth agents are spawned.
7. No `analysis_*.md`, inventory, depth, verification, scoring, or report artifacts are required by Phase 2.
8. No legacy checkpoint is written.
9. Unit tests pass with mocked runners.
10. A manual smoke test can produce a valid `spawn_manifest.md`.

Recommended Phase 3:

```text
recon -> instantiate -> breadth
```

At that point, start addressing:

- worktree isolation
- parallel worker policy
- richer resume semantics
- compatibility with legacy artifact gates

## Migration Strategy

Keep both engines side by side until the LangGraph path is proven.

Future CLI shape:

```bash
plamen core /path/to/project --engine legacy
plamen core /path/to/project --engine langgraph
```

or:

```bash
PLAMEN_ENGINE=langgraph plamen core /path/to/project
```

Do not change the default engine until:

- SC light mode passes end to end
- resume behavior is equivalent or better
- artifact gates are equivalent
- failure handling is tested
- there is a migration path for existing `.scratchpad` runs
