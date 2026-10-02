"""Group consecutive burst frames and select their sharpest previews."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List


@dataclass
class PhotoItem:
    raw_path: Path
    preview_path: Path
    timestamp: datetime
    sharpness: float
    phash: Any
    cluster_id: int
    is_pick: bool = False
    is_reject: bool = False


def group_and_rank_bursts(
    items: List[PhotoItem],
    max_time_delta_sec: float = 3.0,
    max_hash_diff: int = 6,
) -> List[List[PhotoItem]]:
    """Group by adjacent time/hash distances, then update selection flags.

    Cluster IDs start at zero. Equal sharpness scores select the earliest
    frame. The input list's order is preserved; its items are updated in place.
    """
    clusters: List[List[PhotoItem]] = []
    for item in sorted(items, key=lambda photo: photo.timestamp):
        if clusters:
            previous = clusters[-1][-1]
            same_burst = (
                (item.timestamp - previous.timestamp).total_seconds()
                <= max_time_delta_sec
                and item.phash - previous.phash <= max_hash_diff
            )
        else:
            same_burst = False

        if not same_burst:
            clusters.append([])
        item.cluster_id = len(clusters) - 1
        clusters[-1].append(item)

    for cluster in clusters:
        pick = max(cluster, key=lambda photo: photo.sharpness)
        for item in cluster:
            item.is_pick = item is pick
            item.is_reject = item is not pick

    return clusters
