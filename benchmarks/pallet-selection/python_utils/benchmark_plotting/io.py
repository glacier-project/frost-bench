"""Filesystem helpers: input-path resolution, file discovery, metric extraction."""

from __future__ import annotations

import os
import re
from pathlib import Path

UTILS_DIR = Path(__file__).resolve().parent.parent


def resolve_input_path(path_str: str, anchor: Path = UTILS_DIR) -> Path:
    """Resolve a user-supplied path against CWD first, then the python_utils dir."""
    candidate = Path(path_str).expanduser()
    if candidate.is_absolute():
        return candidate

    cwd_path = candidate.resolve()
    if cwd_path.exists():
        return cwd_path

    anchor_path = (anchor / candidate).resolve()
    if anchor_path.exists():
        return anchor_path

    return cwd_path


def get_all_files(
    root: str,
    extensions: list[str] | str,
    pattern_include: str = "",
    pattern_exclude: str = "",
) -> list[str]:
    """Walk ``root`` recursively and return files matching the criteria.

    Args:
        root: Root directory to search.
        extensions: File extension(s) to keep (e.g. ``".json"`` or ``[".json", ".csv"]``).
        pattern_include: If non-empty, only paths containing this substring are kept.
        pattern_exclude: If non-empty, paths containing this substring are dropped.
    """
    if isinstance(extensions, str):
        extensions = [extensions]
    matched: list[str] = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            if not any(fullpath.endswith(ext) for ext in extensions):
                continue
            if pattern_include and pattern_include not in fullpath:
                continue
            if pattern_exclude and pattern_exclude in fullpath:
                continue
            matched.append(fullpath)
    return matched


def find_json_files(directory: str, anchor: Path = UTILS_DIR) -> list[str]:
    """Recursively find every ``*.json`` under ``directory`` (path-resolved)."""
    return [str(path) for path in resolve_input_path(directory, anchor).rglob("*.json")]


def extract_metric_name(filepath: str, metrics: list[str]) -> str | None:
    """Pull the metric token (e.g. ``ID``) out of a result file's stem."""
    pattern = "|".join(re.escape(metric) for metric in metrics)
    match = re.search(rf"_({pattern})_", Path(filepath).stem)
    return match.group(1) if match else None
