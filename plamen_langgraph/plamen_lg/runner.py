from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CodexRunResult:
    stdout_path: str
    stderr_path: str
    events_path: str
    last_message_path: str
    returncode: int | None
    started_at: str
    finished_at: str
    duration_s: float
    timed_out: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class CodexRunner:
    """Non-interactive Codex CLI wrapper for one Phase-1 worker."""

    def __init__(self, codex_bin: str = "codex") -> None:
        self.codex_bin = codex_bin

    def build_command(
        self,
        project_root: str | Path,
        prompt: str,
        last_message_path: str | Path,
    ) -> list[str]:
        return [
            self.codex_bin,
            "exec",
            "-C",
            str(project_root),
            "--sandbox",
            "workspace-write",
            "--json",
            "--output-last-message",
            str(last_message_path),
            prompt,
        ]

    def run(
        self,
        prompt: str,
        project_root: str | Path,
        scratchpad: str | Path,
        output_paths: dict[str, str | Path],
        timeout_s: int,
    ) -> CodexRunResult:
        scratch = Path(scratchpad)
        scratch.mkdir(parents=True, exist_ok=True)

        stdout_path = Path(output_paths["stdout_path"])
        stderr_path = Path(output_paths["stderr_path"])
        events_path = Path(output_paths["events_path"])
        last_message_path = Path(output_paths["last_message_path"])

        started_at = utc_now()
        started = time.monotonic()
        cmd = self.build_command(project_root, prompt, last_message_path)

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(project_root),
                text=True,
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
            events_path.write_text(stdout, encoding="utf-8")
            finished_at = utc_now()
            return CodexRunResult(
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                events_path=str(events_path),
                last_message_path=str(last_message_path),
                returncode=completed.returncode,
                started_at=started_at,
                finished_at=finished_at,
                duration_s=round(time.monotonic() - started, 3),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
            events_path.write_text(stdout, encoding="utf-8")
            finished_at = utc_now()
            return CodexRunResult(
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                events_path=str(events_path),
                last_message_path=str(last_message_path),
                returncode=None,
                started_at=started_at,
                finished_at=finished_at,
                duration_s=round(time.monotonic() - started, 3),
                timed_out=True,
                error=f"codex exec timed out after {timeout_s}s",
            )
