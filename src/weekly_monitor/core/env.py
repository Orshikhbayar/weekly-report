"""Runtime environment loading for local secrets (.env style files)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_env_files() -> list[Path]:
    """Return the default env-file search order.

    Earlier files win because values are only set when a variable is not
    already present in the process environment.
    """
    return [
        Path.cwd() / ".env",
        Path.home() / ".config" / "weekly-monitor" / "env",
        Path.home() / ".config" / "weekly-monitor" / ".env",
    ]


def load_runtime_env(files: Iterable[Path] | None = None) -> list[Path]:
    """Load key/value pairs into ``os.environ`` from known local files.

    Existing process environment values are never overridden.

    Returns the list of files that were read successfully.
    """
    loaded: list[Path] = []
    seen: set[Path] = set()

    for path in (files or default_env_files()):
        p = Path(path).expanduser()
        if p in seen:
            continue
        seen.add(p)
        if not p.is_file():
            continue
        try:
            _load_env_file(p)
            loaded.append(p)
        except Exception:
            # Non-fatal: a broken local env file should not block report runs.
            continue

    return loaded


def _load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export "):].strip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    if not _ENV_KEY_RE.match(key):
        return None

    value = value.strip()
    if not value:
        return key, ""

    # Remove inline comments only when value is unquoted.
    if not (value.startswith("'") or value.startswith('"')):
        hash_pos = value.find("#")
        if hash_pos != -1:
            value = value[:hash_pos].rstrip()

    # Unquote simple quoted values.
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"'", '"'}
    ):
        value = value[1:-1]

    return key, value
