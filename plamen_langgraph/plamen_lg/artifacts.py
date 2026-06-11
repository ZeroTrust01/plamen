from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_artifacts(scratchpad: str | Path, expected_artifacts: list[str]) -> dict[str, Any]:
    """Check expected phase artifacts under the scratchpad.

    Glob patterns are supported so this checker can reuse legacy Phase
    definitions without assuming every artifact name is literal.
    """
    root = Path(scratchpad)
    present: list[dict[str, Any]] = []
    missing: list[str] = []
    seen: set[Path] = set()

    for pattern in expected_artifacts:
        matches = sorted(p for p in root.glob(pattern) if p.is_file())
        if not matches:
            missing.append(pattern)
            continue
        for path in matches:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            present.append(
                {
                    "path": str(path),
                    "exists": True,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

    records = list(present)
    for pattern in missing:
        records.append(
            {
                "path": str(root / pattern),
                "exists": False,
                "size_bytes": None,
                "sha256": None,
            }
        )

    return {
        "ok": not missing,
        "missing": missing,
        "present": present,
        "records": records,
    }


def _strip_markdown(value: str) -> str:
    return re.sub(r"[*`]", "", value or "").strip()


def _split_markdown_table_row(row: str) -> list[str]:
    return [_strip_markdown(cell).strip() for cell in row.strip().strip("|").split("|")]


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _strip_markdown(value).lower()).strip("_")


def _is_separator_row(row: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?[\s|:\-]+\|?\s*", row.strip()))


def _row_from_cells(headers: list[str], cells: list[str]) -> dict[str, str]:
    return {headers[i]: cells[i].strip() for i in range(min(len(headers), len(cells)))}


def _is_no_required(value: str) -> bool:
    return bool(re.match(r"(?i)^(?:no|n|false|skip|optional|merged)\b", value.strip()))


def _is_breadth_output(filename: str) -> bool:
    name = Path(_strip_markdown(filename)).name
    reserved_prefixes = (
        "analysis_rescan_",
        "analysis_percontract_",
        "analysis_merged_into_",
        "analysis_report_",
    )
    if any(name.startswith(prefix) for prefix in reserved_prefixes):
        return False
    return bool(re.fullmatch(r"analysis_[A-Za-z0-9][A-Za-z0-9_.-]*\.md", name))


def _slug_to_analysis_filename(value: str) -> str | None:
    explicit = re.search(r"\b([A-Za-z0-9_.-]+\.md)\b", _strip_markdown(value))
    if explicit:
        return Path(explicit.group(1)).name
    slug = re.sub(r"[^A-Za-z0-9]+", "_", _strip_markdown(value).lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        return None
    if slug.startswith("analysis_"):
        return f"{slug}.md"
    return f"analysis_{slug}.md"


def _first_spawn_table(text: str) -> tuple[list[str], list[dict[str, str]]] | None:
    in_table = False
    headers: list[str] = []
    rows: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not in_table:
            if line.startswith("|"):
                candidate_headers = [
                    _normalize_header(cell) for cell in _split_markdown_table_row(line)
                ]
                if "template" in candidate_headers and any(
                    header in candidate_headers for header in ("required", "required_")
                ):
                    headers = candidate_headers
                    in_table = True
            continue
        if not line.startswith("|"):
            break
        if _is_separator_row(line):
            continue
        cells = _split_markdown_table_row(line)
        if cells:
            rows.append(_row_from_cells(headers, cells))
    return (headers, rows) if in_table else None


def _row_is_spawned_agent(row: dict[str, str]) -> bool:
    row_type = (row.get("row_type") or row.get("type") or row.get("kind") or "").lower()
    if row_type:
        return row_type == "agent" or "breadth agent" in row_type
    explicit_output = _row_output_filename(row)
    if explicit_output and _is_breadth_output(explicit_output):
        return True
    agent_id = row.get("agent_id") or row.get("agent") or ""
    status = (row.get("status") or row.get("spawn_status") or "").lower()
    return bool(agent_id and re.search(r"\b(?:queued|spawned|agent|assigned)\b", status))


def _row_output_filename(row: dict[str, str]) -> str | None:
    for key in (
        "expected_output",
        "output",
        "output_file",
        "filename",
        "file",
        "artifact",
        "expected_file",
    ):
        if row.get(key):
            return _slug_to_analysis_filename(row[key])
    for key in ("focus_area", "focus", "agent_id", "agent", "template"):
        if row.get(key):
            return _slug_to_analysis_filename(row[key])
    return None


def validate_spawn_manifest_schema(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    path = root / "spawn_manifest.md"
    if not path.exists():
        return ["spawn_manifest.md missing"]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"spawn_manifest.md unreadable: {exc}"]
    if path.stat().st_size < 50:
        return ["spawn_manifest.md is a stub (<50 bytes)"]

    forbidden = sorted(
        set(
            re.findall(
                r"\b(?:verify_[A-Za-z0-9_.-]*|analysis_rescan_[A-Za-z0-9_.-]+|"
                r"analysis_percontract_[A-Za-z0-9_.-]+|"
                r"analysis_merged_into_[A-Za-z0-9_.-]+|"
                r"findings_inventory|inventory|depth_[A-Za-z0-9_.-]+|"
                r"chain_[A-Za-z0-9_.-]+|report_[A-Za-z0-9_.-]+)\.md\b",
                text,
            )
        )
    )

    parsed = _first_spawn_table(text)
    if parsed is None:
        suffix = ""
        if forbidden:
            suffix = "; non-breadth artifact rows present: " + ", ".join(forbidden[:8])
        return [
            "spawn_manifest.md schema invalid: no markdown table with Template "
            "and Required? columns" + suffix
        ]

    _headers, rows = parsed
    issues: list[str] = []
    if forbidden:
        issues.append(
            "spawn_manifest.md contains non-breadth artifact row(s): "
            + ", ".join(forbidden[:8])
        )

    agent_ids: set[str] = set()
    outputs: set[str] = set()
    spawned_count = 0
    for row in rows:
        required = row.get("required") or row.get("required_") or row.get("required?")
        if required and _is_no_required(required):
            continue
        if not _row_is_spawned_agent(row):
            continue
        spawned_count += 1
        agent_id = _strip_markdown(row.get("agent_id") or row.get("agent") or "")
        if not agent_id:
            issues.append("spawn_manifest.md has AGENT row without Agent ID")
        elif agent_id.lower() in agent_ids:
            issues.append(f"spawn_manifest.md has duplicate Agent ID: {agent_id}")
        else:
            agent_ids.add(agent_id.lower())

        output = _row_output_filename(row)
        if not output or not _is_breadth_output(output):
            issues.append(
                f"spawn_manifest.md AGENT row {agent_id or '<missing>'} lacks "
                "a first-pass analysis_*.md output"
            )
        elif output in outputs:
            issues.append(f"spawn_manifest.md has duplicate output file: {output}")
        else:
            outputs.add(output)

    if spawned_count <= 0:
        issues.append(
            "spawn_manifest.md schema invalid: no parseable spawned breadth-agent rows"
        )
    if spawned_count and len(outputs) != spawned_count:
        issues.append(
            "spawn_manifest.md maps spawned breadth agents to "
            f"{len(outputs)} unique output file(s) for {spawned_count} spawned agent row(s)"
        )
    return issues


def validate_phase_artifacts(
    phase_name: str,
    scratchpad: str | Path,
    records: list[dict[str, Any]],
) -> list[str]:
    del records
    if phase_name == "recon":
        return []
    if phase_name == "instantiate":
        return validate_spawn_manifest_schema(scratchpad)
    raise ValueError(f"unsupported LangGraph phase: {phase_name}")
