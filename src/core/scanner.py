"""Recursive discovery of visible camera RAW files."""

import os
import stat
from pathlib import Path
from typing import List

SUPPORTED_EXTENSIONS = frozenset({".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf", ".rw2"})


def _is_hidden_or_system(path: Path) -> bool:
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return path.name.startswith(".") or bool(
        attributes & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM)
    )


def scan_directory(path: Path) -> List[Path]:
    """Return sorted RAW paths, pruning hidden/system directories and files.

    Missing roots and non-directory roots raise the corresponding OS exception.
    Directory symlinks are not followed, avoiding recursive cycles.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_dir():
        raise NotADirectoryError(path)
    if _is_hidden_or_system(path):
        return []
    result: List[Path] = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    for directory, directories, files in os.walk(path, onerror=raise_walk_error):
        parent = Path(directory)
        directories[:] = [
            name for name in directories
            if not _is_hidden_or_system(parent / name)
        ]
        for name in files:
            candidate = parent / name
            if candidate.suffix.lower() in SUPPORTED_EXTENSIONS and not _is_hidden_or_system(candidate):
                result.append(candidate)
    return sorted(result, key=lambda item: (str(item).casefold(), str(item)))
