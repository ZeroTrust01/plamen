from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


VALID_LANGUAGES = {"auto", "evm", "solana", "aptos", "sui", "soroban"}
DEFAULT_SCRATCHPAD_DIR = ".lg_scratchpad"


@dataclass(frozen=True)
class AuditConfig:
    project_root: str
    scratchpad: str
    db_path: str
    pipeline: str = "sc"
    mode: str = "core"
    language: str = "evm"
    codex_bin: str = "codex"
    timeout_s: int = 3000

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_small_text(path: Path, max_bytes: int = 65536) -> str:
    try:
        with path.open("rb") as f:
            return f.read(max_bytes).decode("utf-8", errors="ignore")
    except OSError:
        return ""


def detect_language(project_root: str | Path) -> str:
    """Best-effort smart-contract language detection for Phase 1."""
    root = Path(project_root)
    if (root / "Anchor.toml").exists():
        return "solana"
    if (root / "foundry.toml").exists() or any(root.rglob("*.sol")):
        return "evm"

    move_toml = root / "Move.toml"
    if move_toml.exists():
        text = _read_small_text(move_toml).lower()
        if "sui" in text:
            return "sui"
        return "aptos"

    for cargo in root.rglob("Cargo.toml"):
        text = _read_small_text(cargo).lower()
        if "soroban-sdk" in text:
            return "soroban"
        if "anchor-lang" in text or "solana-program" in text:
            return "solana"

    return "evm"


def build_config(
    project_root: str | Path,
    scratchpad: str | Path | None = None,
    db_path: str | Path | None = None,
    pipeline: str = "sc",
    mode: str = "core",
    language: str = "auto",
    codex_bin: str = "codex",
    timeout_s: int = 3000,
) -> AuditConfig:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"project_root must be an existing directory: {root}")
    if pipeline != "sc":
        raise ValueError("Phase 1 supports only the smart-contract pipeline: sc")
    if mode not in {"light", "core", "thorough"}:
        raise ValueError(f"invalid mode: {mode}")
    if language not in VALID_LANGUAGES:
        raise ValueError(f"invalid language: {language}")

    sp = (
        Path(scratchpad).expanduser().resolve()
        if scratchpad
        else root / DEFAULT_SCRATCHPAD_DIR
    )
    db = Path(db_path).expanduser().resolve() if db_path else sp / "plamen_lg.sqlite"
    resolved_language = detect_language(root) if language == "auto" else language

    return AuditConfig(
        project_root=str(root),
        scratchpad=str(sp),
        db_path=str(db),
        pipeline=pipeline,
        mode=mode,
        language=resolved_language,
        codex_bin=codex_bin,
        timeout_s=timeout_s,
    )
