from __future__ import annotations

import hashlib
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

