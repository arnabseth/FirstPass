"""Extract embedded RAW previews and cache JPEGs without changing originals."""

import os
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import exifread
import rawpy
from PIL import Image, ImageOps

DATE_TIME_ORIGINAL = 36867
EXIF_IFD = 34665


def _parse_timestamp(value: object) -> Optional[datetime]:
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    try:
        return datetime.strptime(str(value).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _image_timestamp(image: Image.Image) -> Optional[datetime]:
    exif = image.getexif()
    value = exif.get(DATE_TIME_ORIGINAL)
    if value is None and EXIF_IFD in exif:
        value = exif.get_ifd(EXIF_IFD).get(DATE_TIME_ORIGINAL)
    return _parse_timestamp(value)


def _raw_timestamp(path: Path) -> Optional[datetime]:
    try:
        with path.open("rb") as stream:
            tags = exifread.process_file(stream, stop_tag="DateTimeOriginal", details=False)
        return _parse_timestamp(tags.get("EXIF DateTimeOriginal"))
    except (OSError, ValueError, TypeError, IndexError, KeyError, OverflowError):
        return None


def _render_preview(raw: rawpy.RawPy) -> Image.Image:
    try:
        pixels = raw.postprocess(half_size=True, fast_render=True)
    except TypeError as error:
        if "fast_render" not in str(error):
            raise
        # rawpy Params has no fast_render keyword in current releases.
        # Half-size output bypasses interpolation; LINEAR keeps processing cheap.
        pixels = raw.postprocess(
            half_size=True, demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR,
            no_auto_bright=True, output_bps=8,
        )
    image = Image.fromarray(pixels).convert("RGB")
    bounds = (1920, 1080) if image.width >= image.height else (1080, 1920)
    image.thumbnail(bounds, Image.Resampling.LANCZOS)
    return image


def extract_embedded_jpeg(
    raw_path: Path, cache_dir: Path,
) -> Tuple[Path, Optional[datetime]]:
    """Return a cached JPEG and EXIF capture time (None if absent/invalid).

    The requested built-in hash naming scheme is process-specific: Python may
    choose a different filename after restart. Cache entries older than the RAW
    source are regenerated. Invalid RAW data propagates rawpy's decoding error.
    """
    raw_path, cache_dir = Path(raw_path), Path(cache_dir)
    source_stat = raw_path.stat()
    if not raw_path.is_file():
        raise IsADirectoryError(raw_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{raw_path.stem}_{hash(raw_path.name)}.jpg"
    timestamp = _raw_timestamp(raw_path)
    if cached.is_file() and cached.stat().st_mtime_ns >= source_stat.st_mtime_ns:
        try:
            with Image.open(cached) as image:
                cached_timestamp = _image_timestamp(image)
                image.verify()
            return cached, timestamp or cached_timestamp
        except (OSError, ValueError, SyntaxError):
            pass  # A damaged cache entry is regenerated from the source.

    with rawpy.imread(str(raw_path)) as raw:
        try:
            thumb = raw.extract_thumb()
            if thumb.format != rawpy.ThumbFormat.JPEG:
                raise ValueError("Embedded thumbnail is not JPEG")
            with Image.open(BytesIO(thumb.data)) as embedded:
                timestamp = timestamp or _image_timestamp(embedded)
                image = ImageOps.exif_transpose(embedded).convert("RGB")
        except (rawpy.LibRawError, OSError, ValueError, SyntaxError):
            image = _render_preview(raw)

    exif = Image.Exif()
    if timestamp is not None:
        exif[EXIF_IFD] = {DATE_TIME_ORIGINAL: timestamp.strftime("%Y:%m:%d %H:%M:%S")}
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".jpg", delete=False) as stream:
            temporary_path = Path(stream.name)
            image.save(stream, format="JPEG", quality=85, exif=exif)
        os.replace(temporary_path, cached)
    finally:
        image.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return cached, timestamp
