"""Offline black-box subprocess runners for ``cts_factory.cli`` and ``reel.py``.

Always invokes ``uv run --offline --no-project --with ...`` and blanks API keys
by default (``GEMINI_API_KEY=""``, ``GOOGLE_API_KEY=""``) so dotenv auto-loaders
cannot reload the real repo's ``.env`` or spend API quota. Never imports from
``src/`` or ``cts_factory``.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .discovery import get_project_root, get_real_repo_root
from .text_checks import scan_text_for_secrets

OFFLINE_CLI_WITH: tuple[str, ...] = (
    "pillow",
    "numpy",
    "google-genai",
    "faster-whisper",
    "rapidocr",
    "onnxruntime",
    "imageio-ffmpeg",
)

OFFLINE_REEL_WATCH_WITH: tuple[str, ...] = (
    "pillow",
    "numpy",
    "faster-whisper",
    "rapidocr",
    "onnxruntime",
    "imageio-ffmpeg",
)

_REEL_DIR_RE = re.compile(r"^REEL_DIR:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class CliResult:
    """Captured output and timing of an opaque-box CLI subprocess call."""

    cmd: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    elapsed_s: float


def _uv_offline_cmd(packages: Sequence[str], python_args: Sequence[str]) -> list[str]:
    cmd: list[str] = ["uv", "run", "--offline", "--no-project"]
    for pkg in packages:
        cmd.extend(["--with", pkg])
    cmd.append("python")
    cmd.extend(python_args)
    return cmd


def _build_env(
    *,
    strip_api_keys: bool,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    if strip_api_keys:
        # Setting empty strings (instead of popping) ensures load_dotenv()
        # skips reloading real repo .env keys while bool(os.environ.get(...)) is False.
        env["GEMINI_API_KEY"] = ""
        env["GOOGLE_API_KEY"] = ""
        env["CTS_OFFLINE_TEST"] = "1"
        env["HF_HUB_OFFLINE"] = "1"
    if extra_env:
        env.update(extra_env)
    return env


def run_cli(
    args: Sequence[str],
    *,
    project_root: Path | None = None,
    extra_env: dict[str, str] | None = None,
    strip_api_keys: bool = True,
    timeout_s: float = 120.0,
) -> CliResult:
    """Run ``python -m cts_factory.cli <args>`` offline via ``uv run --offline --no-project``."""
    target_root = get_project_root(project_root)
    real_root = get_real_repo_root()
    src_dir = (target_root / "src") if (target_root / "src").is_dir() else (real_root / "src")

    env = _build_env(strip_api_keys=strip_api_keys, extra_env=extra_env)
    existing_pp = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pp}" if existing_pp else str(src_dir)

    cmd = _uv_offline_cmd(OFFLINE_CLI_WITH, ["-m", "cts_factory.cli", *args])
    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=str(target_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    elapsed = time.monotonic() - t0
    return CliResult(
        cmd=tuple(cmd),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        elapsed_s=elapsed,
    )


def run_reel_watch(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    reel_home: Path | None = None,
    extra_env: dict[str, str] | None = None,
    strip_api_keys: bool = True,
    timeout_s: float = 120.0,
    with_yt_dlp: bool = False,
) -> CliResult:
    """Run ``.agents/skills/reel-watch/scripts/reel.py <args>`` offline in isolation."""
    real_root = get_real_repo_root()
    script_path = real_root / ".agents" / "skills" / "reel-watch" / "scripts" / "reel.py"
    work_cwd = Path(cwd).resolve() if cwd is not None else get_project_root()

    merged_extra: dict[str, str] = {}
    if reel_home is not None:
        merged_extra["REEL_HOME"] = str(Path(reel_home).resolve())
    if extra_env:
        merged_extra.update(extra_env)

    env = _build_env(strip_api_keys=strip_api_keys, extra_env=merged_extra)
    packages = list(OFFLINE_REEL_WATCH_WITH)
    if with_yt_dlp:
        packages.append("yt-dlp[default,curl-cffi]")

    cmd = _uv_offline_cmd(packages, [str(script_path), *args])
    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=str(work_cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    elapsed = time.monotonic() - t0
    return CliResult(
        cmd=tuple(cmd),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        elapsed_s=elapsed,
    )


def parse_reel_dir(stdout: str) -> Path | None:
    """Extract the ``REEL_DIR: <path>`` output directory printed by ``reel.py``."""
    m = _REEL_DIR_RE.search(stdout or "")
    if not m:
        return None
    raw = m.group(1).strip()
    return Path(raw) if raw else None


def assert_no_secret_in_output(
    result: CliResult, sentinel: str | None = None
) -> None:
    """Assert that neither ``stdout`` nor ``stderr`` leaks API keys or a canary sentinel."""
    extra = [sentinel] if (sentinel and len(sentinel) >= 16) else []
    for stream_name, text in (("stdout", result.stdout), ("stderr", result.stderr)):
        hits = scan_text_for_secrets(text, extra_literals=extra, path=stream_name)
        if hits:
            details = "; ".join(
                f"{h.rule}@{h.path}:{h.line_no} ({h.redacted_preview})" for h in hits
            )
            raise AssertionError(f"Secret leaked in CLI {stream_name}: {details}")
        if sentinel and sentinel in text:
            raise AssertionError(
                f"Canary secret sentinel (len={len(sentinel)}) leaked in CLI {stream_name}"
            )
