"""Recoverable disposal of rejected originals and their cached previews."""

import logging
from pathlib import Path
from typing import List, Tuple

import send2trash

from src.core.clusterer import PhotoItem


class PurgeError(OSError):
    """A trash operation failed after zero or more successful moves."""

    def __init__(self, path, trashed_paths, cause):
        super().__init__(f"Could not send {path} to Trash: {cause}")
        self.trashed_paths = list(trashed_paths)


def purge_rejects(items: List[PhotoItem], dry_run: bool = False) -> Tuple[int, List[Path]]:
    """Trash explicit rejects; dry runs return candidates without changing disk.

    Stop on a failed move, exposing completed moves in PurgeError. Cached
    previews are removed only after successful disposal, and never if their
    paths identify an original or a preview still used by a retained item.
    """
    protected = {Path(item.raw_path).resolve() for item in items}
    protected.update(Path(item.preview_path).resolve() for item in items
                     if item.is_reject is not True)
    paths = []
    seen = set()
    for item in items:
        if item.is_reject is not True:
            continue
        path = Path(item.raw_path)
        identity = path.resolve()
        if identity in seen:
            continue
        if not dry_run:
            try:
                send2trash.send2trash(str(item.raw_path))
            except Exception as exc:
                raise PurgeError(path, paths, exc) from exc
        seen.add(identity)
        paths.append(path)
        if not dry_run:
            for cached_item in items:
                if cached_item.is_reject is not True or Path(cached_item.raw_path).resolve() != identity:
                    continue
                preview = Path(cached_item.preview_path)
                if preview.resolve() not in protected:
                    try:
                        preview.unlink(missing_ok=True)
                    except OSError:
                        logging.getLogger(__name__).warning("Could not remove cached preview %s", preview)
    return len(paths), paths
