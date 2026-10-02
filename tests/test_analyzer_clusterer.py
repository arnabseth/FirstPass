"""Synthetic image analysis and burst selection tests."""

from datetime import datetime, timedelta
from pathlib import Path

import cv2
import imagehash
import numpy as np
import pytest
from PIL import Image

from src.core.analyzer import calculate_sharpness, compute_phash
from src.core.clusterer import PhotoItem, group_and_rank_bursts


def test_calculate_sharpness(tmp_path):
    rows, columns = np.indices((128, 128))
    checkerboard = (((rows // 8 + columns // 8) % 2) * 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(checkerboard, (9, 9), 2.0)
    sharp_path = tmp_path / "sharp.png"
    blur_path = tmp_path / "blur.png"
    Image.fromarray(checkerboard).save(sharp_path)
    Image.fromarray(blurred).save(blur_path)

    sharpness = calculate_sharpness(sharp_path)
    assert isinstance(sharpness, float)
    assert sharpness > calculate_sharpness(blur_path)


@pytest.mark.parametrize("kind", ["missing", "corrupt"])
def test_calculate_sharpness_unreadable(tmp_path, kind):
    path = tmp_path / "unreadable.png"
    if kind == "corrupt":
        path.write_bytes(b"not an image")
    assert calculate_sharpness(path) == 0.0


def test_compute_phash(tmp_path):
    rows, columns = np.indices((128, 128))
    pattern = (((rows // 13 + columns // 17) % 2) * 255).astype(np.uint8)
    paths = [tmp_path / name for name in ("original.png", "identical.png", "inverted.png")]
    for path, pixels in zip(paths, [pattern, pattern.copy(), 255 - pattern]):
        Image.fromarray(pixels).save(path)

    original = compute_phash(paths[0])
    assert isinstance(original, imagehash.ImageHash)
    assert original - compute_phash(paths[1]) == 0
    assert original - compute_phash(paths[2]) > 0


def make_item(index, seconds, sharpness, hash_value="0000000000000000"):
    return PhotoItem(
        raw_path=Path(f"frame_{index}.ARW"),
        preview_path=Path(f"frame_{index}.jpg"),
        timestamp=datetime(2026, 10, 2, 9) + timedelta(seconds=seconds),
        sharpness=sharpness,
        phash=imagehash.hex_to_hash(hash_value),
        cluster_id=-1,
    )


def test_group_and_rank_bursts():
    frames = [
        make_item(0, 0, 20),
        make_item(1, 0.5, 80),
        make_item(2, 1, 40),
        make_item(3, 11, 90),
        make_item(4, 11.5, 30),
    ]
    clusters = group_and_rank_bursts([frames[i] for i in [4, 2, 0, 3, 1]])

    assert clusters == [frames[:3], frames[3:]]
    assert len(clusters) == 2
    assert [item.cluster_id for item in frames] == [0, 0, 0, 1, 1]
    for cluster, expected_pick in zip(clusters, [frames[1], frames[3]]):
        assert expected_pick.is_pick is True
        assert expected_pick.is_reject is False
        for item in cluster:
            if item is not expected_pick:
                assert item.is_pick is False
                assert item.is_reject is True


def test_empty_and_singleton():
    assert group_and_rank_bursts([]) == []
    item = make_item(0, 0, 0)
    item.is_reject = True
    assert group_and_rank_bursts([item]) == [[item]]
    assert item.cluster_id == 0
    assert item.is_pick is True
    assert item.is_reject is False


@pytest.mark.parametrize(
    "seconds,hash_value,expected_count",
    [
        (3.0, "000000000000003f", 1),
        (3.001, "000000000000003f", 2),
        (3.0, "000000000000007f", 2),
    ],
)
def test_burst_thresholds(seconds, hash_value, expected_count):
    frames = [make_item(0, 0, 10), make_item(1, seconds, 20, hash_value)]
    assert len(group_and_rank_bursts(frames)) == expected_count


def test_adjacent_comparisons_custom_thresholds_and_reranking():
    frames = [
        make_item(0, 0, 10),
        make_item(1, 4, 30, "00000000000000ff"),
        make_item(2, 8, 20, "000000000000ffff"),
    ]
    assert group_and_rank_bursts(frames, 4.0, 8) == [frames]
    assert frames[1].is_pick is True

    # Reranking must clear old picks/rejects and replace cluster IDs.
    assert group_and_rank_bursts(frames) == [[item] for item in frames]
    assert [item.cluster_id for item in frames] == [0, 1, 2]
    assert all(item.is_pick and not item.is_reject for item in frames)


def test_equal_sharpness_selects_earliest_frame():
    first = make_item(0, 0, 10)
    second = make_item(1, 1, 10)
    group_and_rank_bursts([second, first])
    assert first.is_pick is True
    assert second.is_reject is True
