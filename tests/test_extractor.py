"""Synthetic RAW decoder tests using real JPEG encoding and rawpy parameters."""

import os
import stat
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
import rawpy
from PIL import Image

from src.core import extractor, scanner


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "capture.ARW"
    path.write_bytes(b"synthetic RAW placeholder")
    return path


@pytest.fixture
def decoder(monkeypatch):
    stream = BytesIO()
    exif = Image.Exif()
    exif[34665] = {36867: "2026:10:02 09:10:11"}
    Image.new("RGB", (96, 64), (100, 150, 200)).save(stream, "JPEG", exif=exif)
    raw = MagicMock()
    raw.__enter__.return_value = raw
    raw.extract_thumb.return_value = SimpleNamespace(format=rawpy.ThumbFormat.JPEG, data=stream.getvalue())
    # Validate fallback kwargs against the actual installed rawpy API.
    def render(**kwargs):
        rawpy.Params(**kwargs)
        return np.zeros((1200, 2400, 3), dtype=np.uint8)
    raw.postprocess.side_effect = render
    reader = MagicMock(return_value=raw)
    monkeypatch.setattr(extractor.rawpy, "imread", reader)
    return raw, reader


def test_embedded_jpeg_and_cache_reuse(source, tmp_path, decoder):
    raw, reader = decoder
    cache = tmp_path / "nested" / "cache"
    preview, timestamp = extractor.extract_embedded_jpeg(source, cache)
    assert preview == cache / f"{source.stem}_{hash(source.name)}.jpg"
    assert timestamp == datetime(2026, 10, 2, 9, 10, 11)
    with Image.open(preview) as image:
        assert image.format == "JPEG"
        assert image.size == (96, 64)
        assert image.mode == "RGB"
        assert extractor._image_timestamp(image) == timestamp
        assert image.getpixel((40, 30)) == pytest.approx((100, 150, 200), abs=3)
    assert extractor.extract_embedded_jpeg(source, cache) == (preview, timestamp)
    reader.assert_called_once_with(str(source))
    raw.postprocess.assert_not_called()
    raw.__exit__.assert_called_once()
    assert list(cache.iterdir()) == [preview]


@pytest.mark.parametrize("failure", ["missing", "unsupported", "corrupt"])
def test_fallback_is_1080p_and_uses_real_rawpy_parameters(source, tmp_path, decoder, failure):
    raw, _ = decoder
    if failure == "missing":
        raw.extract_thumb.side_effect = rawpy.LibRawNoThumbnailError()
    elif failure == "unsupported":
        raw.extract_thumb.return_value.format = rawpy.ThumbFormat.BITMAP
    else:
        raw.extract_thumb.return_value.data = b"invalid JPEG"
    preview, timestamp = extractor.extract_embedded_jpeg(source, tmp_path / "cache")
    assert timestamp is None
    with Image.open(preview) as image:
        assert image.size == (1920, 960)
    assert raw.postprocess.call_args_list[0].kwargs == {"half_size": True, "fast_render": True}
    assert raw.postprocess.call_args_list[1].kwargs["half_size"] is True


def test_raw_exif_timestamp_takes_priority(source, tmp_path, decoder, monkeypatch):
    monkeypatch.setattr(extractor.exifread, "process_file", lambda *a, **kw: {"EXIF DateTimeOriginal": "2025:06:07 08:09:10"})
    _, timestamp = extractor.extract_embedded_jpeg(source, tmp_path / "cache")
    assert timestamp == datetime(2025, 6, 7, 8, 9, 10)


@pytest.mark.parametrize("value", [None, "", "bad date", "2026:99:02 00:00:00"])
def test_invalid_timestamp(value):
    assert extractor._parse_timestamp(value) is None


def test_stale_cache_is_refreshed(source, tmp_path, decoder):
    raw, reader = decoder
    cache = tmp_path / "cache"
    preview, _ = extractor.extract_embedded_jpeg(source, cache)
    os.utime(preview, ns=(1, 1))
    extractor.extract_embedded_jpeg(source, cache)
    assert reader.call_count == 2
    assert raw.extract_thumb.call_count == 2


def test_corrupt_cache_is_rebuilt(source, tmp_path, decoder):
    _, reader = decoder
    cache = tmp_path / "cache"
    preview, _ = extractor.extract_embedded_jpeg(source, cache)
    preview.write_bytes(b"corrupt cache")
    extractor.extract_embedded_jpeg(source, cache)
    assert reader.call_count == 2
    with Image.open(preview) as image:
        image.verify()


@pytest.mark.parametrize("kind,exception", [("missing", FileNotFoundError), ("directory", IsADirectoryError)])
def test_invalid_path(tmp_path, decoder, kind, exception):
    _, reader = decoder
    path = tmp_path / "invalid.ARW"
    if kind == "directory":
        path.mkdir()
    with pytest.raises(exception):
        extractor.extract_embedded_jpeg(path, tmp_path / "cache")
    reader.assert_not_called()
    assert not (tmp_path / "cache").exists()


def test_invalid_raw_data_raises_without_decoder_mock(source, tmp_path):
    with pytest.raises(rawpy.LibRawError):
        extractor.extract_embedded_jpeg(source, tmp_path / "cache")
    assert list((tmp_path / "cache").iterdir()) == []


def test_render_failure_propagates(source, tmp_path, decoder):
    raw, _ = decoder
    raw.extract_thumb.side_effect = rawpy.LibRawNoThumbnailError()
    raw.postprocess.side_effect = rawpy.LibRawError("render failed")
    with pytest.raises(rawpy.LibRawError):
        extractor.extract_embedded_jpeg(source, tmp_path / "cache")
    assert list((tmp_path / "cache").iterdir()) == []
    raw.__exit__.assert_called_once()


def test_jpeg_quality_is_85(source, tmp_path, decoder, monkeypatch):
    save = Image.Image.save
    qualities = []
    def record_save(image, *args, **kwargs):
        qualities.append(kwargs.get("quality"))
        return save(image, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "save", record_save)
    extractor.extract_embedded_jpeg(source, tmp_path / "cache")
    assert qualities == [85]


def test_scan_all_extensions_recursively_and_prune_hidden(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    expected = []
    for extension in ["ARW", "cr2", "Cr3", "NEF", "DNG", "RAF", "RW2"]:
        path = nested / f"capture.{extension}"
        path.touch()
        expected.append(path)
    (nested / "image.jpg").touch()
    (nested / ".hidden.ARW").touch()
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "capture.ARW").touch()
    assert scanner.scan_directory(tmp_path) == sorted(expected, key=lambda p: (str(p).casefold(), str(p)))


@pytest.mark.parametrize("attribute", [stat.FILE_ATTRIBUTE_HIDDEN, stat.FILE_ATTRIBUTE_SYSTEM])
def test_windows_attributes_filter_files_and_directories(tmp_path, monkeypatch, attribute):
    hidden_file = tmp_path / "hidden.ARW"
    hidden_file.touch()
    hidden_dir = tmp_path / "hidden_folder"
    hidden_dir.mkdir()
    (hidden_dir / "nested.ARW").touch()
    real_stat = Path.stat
    def fake_stat(path, *args, **kwargs):
        if path in (hidden_file, hidden_dir):
            return SimpleNamespace(st_file_attributes=attribute)
        return real_stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", fake_stat)
    assert scanner.scan_directory(tmp_path) == []


def test_scan_invalid_root(tmp_path):
    with pytest.raises(FileNotFoundError):
        scanner.scan_directory(tmp_path / "missing")
    file = tmp_path / "capture.ARW"
    file.touch()
    with pytest.raises(NotADirectoryError):
        scanner.scan_directory(file)
