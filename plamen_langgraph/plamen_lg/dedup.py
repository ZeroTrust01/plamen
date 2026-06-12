from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


FINDING_ID_RE = r"[A-Z][A-Z0-9_-]*-\d+"
LIVE_PAIR_LIMIT = 24
INVENTORY_BUDGET_GUARD_COUNT = 180


@dataclass(frozen=True)
class InventoryFinding:
    finding_id: str
    title: str
    severity: str
    location: str
    source_ids: str
    block: str
    file_part: str
    line_range: tuple[int, int] | None


@dataclass(frozen=True)
class DedupPair:
    left: InventoryFinding
    right: InventoryFinding
    title_score: float
    signal: str


def _field(body: str, label: str) -> str:
    patterns = [
        rf"(?im)^\s*\*\*{re.escape(label)}\*\*\s*:\s*(.+?)\s*$",
        rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$",
        rf"(?im)^\s*\|\s*{re.escape(label)}\s*\|\s*(.+?)\s*\|",
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return re.sub(r"[*`]", "", match.group(1)).strip()
    return ""


def _normalize_location(location: str) -> str:
    return re.sub(r"[`*]", "", location or "").strip()


def _location_file(location: str) -> str:
    normalized = _normalize_location(location)
    match = re.search(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)", normalized)
    return match.group(1).lower() if match else ""


def _location_range(location: str) -> tuple[int, int] | None:
    nums = [int(value) for value in re.findall(r"(?i)(?:^|[:\s,-])L?(\d+)\b", location)]
    if not nums:
        return None
    return min(nums), max(nums)


def _ranges_near(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] <= right[1] + 15 and right[0] <= left[1] + 15


def _title_tokens(title: str) -> set[str]:
    stop = {
        "a",
        "an",
        "and",
        "by",
        "for",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
    return {
        token
        for token in re.findall(r"[A-Za-z0-9_]{3,}", title.lower())
        if token not in stop
    }


def _title_score(left: str, right: str) -> float:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def parse_inventory_findings(scratchpad: str | Path) -> list[InventoryFinding]:
    path = Path(scratchpad) / "findings_inventory.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    heading_re = re.compile(
        rf"(?im)^###\s+(?:Finding\s+)?\[({FINDING_ID_RE})\]:?\s*(.*?)\s*$"
    )
    matches = list(heading_re.finditer(text))
    findings: list[InventoryFinding] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        body = text[match.end() : end]
        finding_id = match.group(1)
        title = match.group(2).strip() or _field(body, "Title") or finding_id
        severity = _field(body, "Severity")
        location = _field(body, "Location")
        source_ids = _field(body, "Source IDs")
        findings.append(
            InventoryFinding(
                finding_id=finding_id,
                title=title,
                severity=severity,
                location=location,
                source_ids=source_ids,
                block=block,
                file_part=_location_file(location),
                line_range=_location_range(location),
            )
        )
    return findings


def _candidate_pairs(findings: list[InventoryFinding]) -> list[DedupPair]:
    pairs: list[DedupPair] = []
    seen: set[tuple[str, str]] = set()
    for i, left in enumerate(findings):
        for right in findings[i + 1 :]:
            key = (left.finding_id, right.finding_id)
            if key in seen:
                continue
            signals: list[str] = []
            if left.file_part and left.file_part == right.file_part:
                if left.line_range and right.line_range and _ranges_near(
                    left.line_range, right.line_range
                ):
                    signals.append(
                        "location proximity "
                        f"(L{left.line_range[0]}-{left.line_range[1]} vs "
                        f"L{right.line_range[0]}-{right.line_range[1]})"
                    )
                score = _title_score(left.title, right.title)
                if score >= 0.50:
                    signals.append(f"title overlap {score:.2f}")
            else:
                score = _title_score(left.title, right.title)
            if left.source_ids and right.source_ids:
                left_sources = set(re.findall(FINDING_ID_RE, left.source_ids))
                right_sources = set(re.findall(FINDING_ID_RE, right.source_ids))
                overlap = left_sources & right_sources
                if overlap:
                    signals.append(
                        "shared source IDs: " + ", ".join(sorted(overlap)[:8])
                    )
            if not signals:
                continue
            seen.add(key)
            pairs.append(DedupPair(left, right, score, " + ".join(signals)))
    return sorted(
        pairs,
        key=lambda pair: (
            -int("shared source" in pair.signal),
            -int("location proximity" in pair.signal),
            -pair.title_score,
            pair.left.finding_id,
            pair.right.finding_id,
        ),
    )


def _write_candidate_files(scratchpad: Path, pairs: list[DedupPair]) -> int:
    live_pairs = pairs[:LIVE_PAIR_LIMIT]
    lines = [
        "# Dedup Candidate Pairs",
        "",
        f"{len(live_pairs)} candidate pair(s) identified for LangGraph semantic review.",
    ]
    if len(pairs) > len(live_pairs):
        lines.extend(
            [
                "",
                f"Bounded work packet: showing top {len(live_pairs)} of {len(pairs)} candidate pair(s).",
                "The full candidate set is preserved in `dedup_candidate_pairs_full.md`.",
                "Treat omitted pairs as deferred, not silently discarded.",
            ]
        )
    lines.extend(
        [
            "",
            "| Finding A | Finding B | Title Score | Signal(s) | Same Sev? |",
            "|-----------|-----------|-------------|-----------|-----------|",
        ]
    )
    for pair in live_pairs:
        same_sev = (
            "Yes"
            if pair.left.severity.lower() == pair.right.severity.lower()
            else "No"
        )
        lines.append(
            f"| {pair.left.finding_id}: {pair.left.title[:50]} | "
            f"{pair.right.finding_id}: {pair.right.title[:50]} | "
            f"{pair.title_score:.2f} | {pair.signal} | {same_sev} |"
        )
    if not live_pairs:
        lines.append("| | | | No candidate duplicate pairs found. | |")
    (scratchpad / "dedup_candidate_pairs.md").write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )

    if len(pairs) > len(live_pairs):
        full_lines = [
            "# Dedup Candidate Pairs",
            "",
            f"{len(pairs)} candidate pair(s) identified for LangGraph semantic review.",
            "",
            "| Finding A | Finding B | Title Score | Signal(s) | Same Sev? |",
            "|-----------|-----------|-------------|-----------|-----------|",
        ]
        for pair in pairs:
            same_sev = (
                "Yes"
                if pair.left.severity.lower() == pair.right.severity.lower()
                else "No"
            )
            full_lines.append(
                f"| {pair.left.finding_id}: {pair.left.title[:50]} | "
                f"{pair.right.finding_id}: {pair.right.title[:50]} | "
                f"{pair.title_score:.2f} | {pair.signal} | {same_sev} |"
            )
        (scratchpad / "dedup_candidate_pairs_full.md").write_text(
            "\n".join(full_lines).rstrip() + "\n",
            encoding="utf-8",
        )

    focus_ids = {
        finding.finding_id for pair in live_pairs for finding in (pair.left, pair.right)
    }
    if focus_ids:
        focus_lines = [
            "# Dedup Focus Inventory",
            "",
            "This bounded packet contains only finding bodies referenced by "
            "`dedup_candidate_pairs.md`.",
            "",
        ]
        for finding in parse_inventory_findings(scratchpad):
            if finding.finding_id in focus_ids:
                focus_lines.append(finding.block)
                focus_lines.append("")
        (scratchpad / "dedup_focus_inventory.md").write_text(
            "\n".join(focus_lines).rstrip() + "\n",
            encoding="utf-8",
        )
    return len(live_pairs)


def write_passthrough_outputs(
    scratchpad: str | Path,
    reason: str,
    *,
    status: str = "PASSTHROUGH",
) -> None:
    root = Path(scratchpad)
    source = root / "findings_inventory.md"
    target = root / "findings_inventory_deduped.md"
    body = source.read_text(encoding="utf-8", errors="replace") if source.exists() else ""
    if not body.strip():
        body = (
            "# Findings Inventory\n\n"
            "## Source Summary\n\nNo source inventory was available.\n\n"
            "## Master Table\n\nNo findings.\n\n"
            "## Per-Finding Detail\n\nNo findings.\n"
        )
    target.write_text(body, encoding="utf-8")
    (root / "dedup_decisions.md").write_text(
        "# Semantic Dedup Decisions\n\n"
        f"**Status**: {status}\n\n"
        f"**Reason**: {reason}.\n\n"
        "LangGraph preserved `findings_inventory.md` unchanged for this phase.\n",
        encoding="utf-8",
    )


def prepare_sc_semantic_dedup(scratchpad: str | Path) -> tuple[bool, str | None]:
    root = Path(scratchpad)
    findings = parse_inventory_findings(root)
    pairs = _candidate_pairs(findings)
    live_pair_count = _write_candidate_files(root, pairs)
    has_likely_dup = False
    inv = root / "findings_inventory.md"
    if inv.exists():
        has_likely_dup = "LIKELY-DUP" in inv.read_text(encoding="utf-8", errors="replace")

    if live_pair_count == 0 and not has_likely_dup:
        reason = "no candidate pairs and no LIKELY-DUP tags"
        write_passthrough_outputs(root, reason)
        return True, reason
    if len(pairs) > LIVE_PAIR_LIMIT or len(findings) > INVENTORY_BUDGET_GUARD_COUNT:
        reason = (
            "semantic dedup budget guard: "
            f"{len(pairs)} candidate pair(s), {len(findings)} inventory finding(s)"
        )
        write_passthrough_outputs(root, reason, status="BUDGET_GUARD_PASSTHROUGH")
        return True, reason

    write_passthrough_outputs(
        root,
        "pre-run passthrough safety net; bounded semantic dedup may overwrite "
        "these artifacts if it completes with valid outputs",
        status="IN_PROGRESS_PASSTHROUGH_WRITTEN",
    )
    return False, None


def _finding_records_payload(scratchpad: Path) -> dict[str, object]:
    records = []
    for finding in parse_inventory_findings(scratchpad):
        records.append(
            {
                "id": finding.finding_id,
                "title": finding.title,
                "severity": finding.severity,
                "location": finding.location,
                "source_ids": finding.source_ids,
            }
        )
    return {
        "schema_version": "plamen.langgraph.finding_records.v1",
        "source": "findings_inventory.md",
        "records": records,
    }


def finalize_sc_semantic_dedup(scratchpad: str | Path) -> list[str]:
    root = Path(scratchpad)
    deduped = root / "findings_inventory_deduped.md"
    active = root / "findings_inventory.md"
    if not deduped.exists():
        return ["sc_semantic_dedup missing deduped inventory for swap"]
    if deduped.stat().st_size <= 100:
        return ["sc_semantic_dedup deduped inventory too small for swap"]
    if active.exists():
        shutil.copy2(active, root / "findings_inventory_pre_dedup.md")
    shutil.copy2(deduped, active)
    (root / "finding_records.json").write_text(
        json.dumps(_finding_records_payload(root), indent=2),
        encoding="utf-8",
    )
    return []
