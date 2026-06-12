from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


BREADTH_MIN_BYTES = 200
RESCAN_MIN_BYTES = 200
INVENTORY_MIN_BYTES = 200
INVENTORY_MAX_SOURCE_FILES = 40
INVENTORY_MAX_SOURCE_BYTES = 512_000
INVENTORY_SOURCE_TOO_LARGE = (
    "inventory source set too large; needs sharded inventory support"
)


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


def _is_forbidden_breadth_output(filename: str) -> bool:
    name = Path(_strip_markdown(filename)).name
    if not name.endswith(".md"):
        return False
    forbidden_prefixes = (
        "analysis_rescan_",
        "analysis_percontract_",
        "analysis_merged_into_",
        "analysis_report_",
        "findings_inventory",
        "inventory",
        "depth_",
        "chain_",
        "verify_",
        "verification_",
        "score",
        "report_",
    )
    return name == "AUDIT_REPORT.md" or any(
        name.startswith(prefix) for prefix in forbidden_prefixes
    )


def _is_rescan_output(filename: str) -> bool:
    name = Path(_strip_markdown(filename)).name
    return bool(re.fullmatch(r"analysis_rescan_[A-Za-z0-9][A-Za-z0-9_.-]*\.md", name))


def _is_percontract_output(filename: str) -> bool:
    name = Path(_strip_markdown(filename)).name
    return bool(
        re.fullmatch(r"analysis_percontract_[A-Za-z0-9][A-Za-z0-9_.-]*\.md", name)
    )


def _is_rescan_owned_output(filename: str) -> bool:
    return _is_rescan_output(filename) or _is_percontract_output(filename)


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


def parse_breadth_outputs(scratchpad: str | Path) -> list[str]:
    """Return manifest-derived first-pass breadth output filenames.

    This intentionally mirrors the legacy parser's accepted table shape while
    keeping LangGraph Phase 3 independent of legacy driver state.
    """
    path = Path(scratchpad) / "spawn_manifest.md"
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    parsed = _first_spawn_table(text)
    if parsed is None:
        return []

    _headers, rows = parsed
    outputs: list[str] = []
    seen: set[str] = set()
    for row in rows:
        required = row.get("required") or row.get("required_") or row.get("required?")
        if required and _is_no_required(required):
            continue
        if not _row_is_spawned_agent(row):
            continue
        output = _row_output_filename(row)
        if not output or not _is_breadth_output(output):
            continue
        if output in seen:
            continue
        seen.add(output)
        outputs.append(output)
    return outputs


def expected_breadth_artifacts(scratchpad: str | Path) -> list[str]:
    return parse_breadth_outputs(scratchpad)


def breadth_open_outputs(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    return [
        name
        for name in expected_breadth_artifacts(root)
        if not (root / name).is_file() or (root / name).stat().st_size < BREADTH_MIN_BYTES
    ]


def first_pass_breadth_issues(scratchpad: str | Path) -> list[str]:
    """Validate manifest-derived first-pass breadth outputs for rescan input.

    Unlike the breadth phase's own validator, this check intentionally does
    not reject existing rescan/per-contract files. That lets a failed rescan
    retry validate the first-pass prerequisite without treating its own prior
    partial outputs as breadth contamination.
    """
    root = Path(scratchpad)
    issues = validate_spawn_manifest_schema(root)
    expected = expected_breadth_artifacts(root)
    if not expected:
        issues.append(
            "spawn_manifest.md schema invalid: zero manifest-derived breadth outputs"
        )
    for name in expected:
        path = root / name
        if not path.exists():
            issues.append(f"missing first-pass breadth artifact: {name}")
        elif path.stat().st_size < BREADTH_MIN_BYTES:
            issues.append(
                f"stub first-pass breadth artifact: {name} "
                f"(<{BREADTH_MIN_BYTES} bytes)"
            )
    return issues


def forbidden_breadth_artifacts(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    if not root.exists():
        return []
    return sorted(
        path.name
        for path in root.glob("*.md")
        if path.is_file() and _is_forbidden_breadth_output(path.name)
    )


def rescan_outputs(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    if not root.exists():
        return []
    return sorted(
        path.name
        for path in root.glob("*.md")
        if path.is_file() and _is_rescan_owned_output(path.name)
    )


def rescan_prerequisite_issues(scratchpad: str | Path) -> list[str]:
    """Validate completed rescan inputs without rejecting inventory retries."""
    root = Path(scratchpad)
    issues = first_pass_breadth_issues(root)

    owned = rescan_outputs(root)
    rescan_family = [name for name in owned if _is_rescan_output(name)]
    percontract_family = [name for name in owned if _is_percontract_output(name)]
    if not rescan_family:
        issues.append("missing rescan artifact family: analysis_rescan_*.md")
    if not percontract_family:
        issues.append("missing per-contract artifact family: analysis_percontract_*.md")

    for name in owned:
        path = root / name
        if path.stat().st_size < RESCAN_MIN_BYTES:
            issues.append(f"stub rescan artifact: {name} (<{RESCAN_MIN_BYTES} bytes)")

    duplicates = duplicate_rescan_outputs_from_first_pass(root)
    if duplicates:
        issues.extend(duplicates)
    return issues


def inventory_source_files(scratchpad: str | Path) -> list[str]:
    """Return the authoritative discovery source list for inventory."""
    root = Path(scratchpad)
    sources: list[str] = []
    seen: set[str] = set()
    for name in expected_breadth_artifacts(root) + rescan_outputs(root):
        if name in seen:
            continue
        seen.add(name)
        sources.append(name)
    return sources


def inventory_source_size_issues(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    sources = inventory_source_files(root)
    total_bytes = 0
    for name in sources:
        path = root / name
        if path.is_file():
            total_bytes += path.stat().st_size
    if (
        len(sources) > INVENTORY_MAX_SOURCE_FILES
        or total_bytes > INVENTORY_MAX_SOURCE_BYTES
    ):
        return [INVENTORY_SOURCE_TOO_LARGE]
    return []


def expected_inventory_artifacts(scratchpad: str | Path) -> list[str]:
    del scratchpad
    return ["findings_inventory.md"]


def forbidden_inventory_artifacts(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    if not root.exists():
        return []
    forbidden: list[str] = []
    downstream_prefixes = (
        "depth_",
        "chain_",
        "verify_",
        "verification_",
        "score",
        "report_",
        "rag_",
        "semantic_",
        "invariant_",
    )
    forbidden_exact = {
        "AUDIT_REPORT.md",
        "confidence_scores.md",
        "findings_inventory_deduped.md",
        "hypotheses.md",
        "chain_hypotheses.md",
        "semantic_invariants.md",
        "inventory_shard_plan.md",
        "variable_finding_map.md",
    }
    for path in root.glob("*.md"):
        if not path.is_file():
            continue
        name = path.name
        if name in {"findings_inventory.md", "violations.md"}:
            continue
        if name.startswith("_lg_"):
            continue
        if name in forbidden_exact:
            forbidden.append(name)
            continue
        if name.startswith("findings_inventory_chunk_"):
            forbidden.append(name)
            continue
        if re.fullmatch(r"inventory_chunk_[A-Za-z0-9_.-]+\.manifest\.md", name):
            forbidden.append(name)
            continue
        if any(name.startswith(prefix) for prefix in downstream_prefixes):
            forbidden.append(name)
    return sorted(set(forbidden))


def forbidden_rescan_artifacts(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    if not root.exists():
        return []
    first_pass = set(expected_breadth_artifacts(root))
    forbidden: list[str] = []
    downstream_prefixes = (
        "findings_inventory",
        "inventory",
        "depth_",
        "chain_",
        "verify_",
        "verification_",
        "score",
        "report_",
    )
    for path in root.glob("*.md"):
        if not path.is_file():
            continue
        name = path.name
        if _is_rescan_owned_output(name):
            continue
        if _is_breadth_output(name) and name not in first_pass:
            forbidden.append(name)
            continue
        if name.startswith("analysis_") and name not in first_pass:
            forbidden.append(name)
            continue
        if name == "AUDIT_REPORT.md" or any(name.startswith(prefix) for prefix in downstream_prefixes):
            forbidden.append(name)
    return sorted(set(forbidden))


def _normalized_file_text(path: Path) -> str:
    try:
        return re.sub(r"\s+", " ", path.read_text(encoding="utf-8", errors="replace")).strip()
    except OSError:
        return ""


def duplicate_rescan_outputs_from_first_pass(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    first_pass_texts = {
        name: _normalized_file_text(root / name)
        for name in expected_breadth_artifacts(root)
        if (root / name).is_file()
    }
    duplicates: list[str] = []
    for name in rescan_outputs(root):
        text = _normalized_file_text(root / name)
        if not text:
            continue
        for first_name, first_text in first_pass_texts.items():
            if text == first_text:
                duplicates.append(f"{name} duplicates first-pass breadth output {first_name}")
                break
    return duplicates


def _markdown_section(text: str, section_name: str) -> str:
    pattern = re.compile(
        rf"(?ims)^#+\s*{re.escape(section_name)}\s*$"
        rf"(.*?)(?=^#+\s+\S|\Z)"
    )
    match = pattern.search(text)
    return match.group(1) if match else ""


def _has_markdown_section(text: str, section_name: str) -> bool:
    return bool(
        re.search(rf"(?im)^#+\s*{re.escape(section_name)}\s*$", text)
        or re.search(rf"(?i)\b{re.escape(section_name)}\b", text)
    )


def _inventory_structure_issues(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    path = root / "findings_inventory.md"
    if not path.exists():
        return ["missing inventory artifact: findings_inventory.md"]
    if path.stat().st_size < INVENTORY_MIN_BYTES:
        return [
            "stub inventory artifact: findings_inventory.md "
            f"(<{INVENTORY_MIN_BYTES} bytes)"
        ]

    text = path.read_text(encoding="utf-8", errors="replace")
    issues: list[str] = []
    required_sections = ["Source Summary", "Master Table", "Per-Finding Detail"]
    for section in required_sections:
        if not _has_markdown_section(text, section):
            issues.append(f"findings_inventory.md missing required section: {section}")

    required_labels = [
        "Finding ID",
        "Title",
        "Severity",
        "Verdict",
        "Location",
        "Source IDs",
        "Root Cause",
        "Preferred Tag",
    ]
    normalized = text.lower()
    for label in required_labels:
        if label.lower() not in normalized:
            issues.append(f"findings_inventory.md missing required field label: {label}")

    source_summary = _markdown_section(text, "Source Summary")
    if not source_summary:
        source_summary = text if _has_markdown_section(text, "Source Summary") else ""
    if source_summary:
        for name in inventory_source_files(root):
            if name not in source_summary:
                issues.append(
                    "findings_inventory.md Source Summary missing discovery source: "
                    f"{name}"
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
    if phase_name == "breadth":
        root = Path(scratchpad)
        issues = validate_spawn_manifest_schema(root)
        expected = expected_breadth_artifacts(root)
        if not expected:
            issues.append(
                "spawn_manifest.md schema invalid: zero manifest-derived breadth outputs"
            )
        for name in expected:
            if _is_forbidden_breadth_output(name):
                issues.append(f"forbidden breadth output family in manifest: {name}")
                continue
            path = root / name
            if not path.exists():
                issues.append(f"missing breadth artifact: {name}")
            elif path.stat().st_size < BREADTH_MIN_BYTES:
                issues.append(
                    f"stub breadth artifact: {name} "
                    f"(<{BREADTH_MIN_BYTES} bytes)"
                )
        forbidden = forbidden_breadth_artifacts(root)
        if forbidden:
            issues.append(
                "breadth phase wrote forbidden later-phase artifact(s): "
                + ", ".join(forbidden[:12])
            )
        return issues
    if phase_name == "rescan":
        root = Path(scratchpad)
        issues = rescan_prerequisite_issues(root)

        forbidden = forbidden_rescan_artifacts(root)
        if forbidden:
            issues.append(
                "rescan phase wrote artifact(s) outside rescan-owned families: "
                + ", ".join(forbidden[:12])
            )
        return issues
    if phase_name == "inventory":
        root = Path(scratchpad)
        issues = rescan_prerequisite_issues(root)
        issues.extend(inventory_source_size_issues(root))
        issues.extend(_inventory_structure_issues(root))
        forbidden = forbidden_inventory_artifacts(root)
        if forbidden:
            issues.append(
                "inventory phase wrote forbidden later-phase or legacy artifact(s): "
                + ", ".join(forbidden[:12])
            )
        return issues
    raise ValueError(f"unsupported LangGraph phase: {phase_name}")
