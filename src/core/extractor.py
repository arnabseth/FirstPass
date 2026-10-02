"""Extract embedded RAW previews and cache JPEGs without changing originals."""

import logging
import mmap
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from pathlib import Path
from threading import RLock
from typing import Optional, Tuple

import exifread
import rawpy
from PIL import Image, ImageOps

DATE_TIME_ORIGINAL = 36867
EXIF_IFD = 34665
logger = logging.getLogger(__name__)
_decoder_lock = RLock()


@contextmanager
def _quiet_libraw():
    """Silence native diagnostics and restore stderr even on decoder failure.

    File-descriptor redirection is process-wide, so serialize our RAW calls.
    A GUI or Python capture stream may have no fileno; LibRaw still uses fd 2.
    """
    with _decoder_lock:
        try:
            descriptor = sys.stderr.fileno()
        except (AttributeError, OSError, ValueError):
            descriptor = 2
        if sys.stderr is not None:
            sys.stderr.flush()
        # pytest/GUI wrappers can expose a descriptor other than C stderr (2).
        # Redirect both so native writes and writes via the Python stream agree.
        saved = {}
        try:
            for target in {2, descriptor}:
                saved[target] = os.dup(target)
            with open(os.devnull, "wb") as sink:
                for target in saved:
                    os.dup2(sink.fileno(), target)
                yield
        finally:
            for target, original in saved.items():
                try:
                    os.dup2(original, target)
                finally:
                    os.close(original)


class _ExifDiagnosticFilter(logging.Filter):
    def filter(self, record):
        # ExifRead also logs this message for unrecognized containers. Report
        # one application warning only when all preview strategies have failed.
        return not record.getMessage().startswith("File format not recognized")


def _parse_timestamp(value: object) -> Optional[datetime]:
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    try:
        return datetime.strptime(str(value).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _image_timestamp(image: Image.Image) -> Optional[datetime]:
    try:
        exif = image.getexif()
        value = exif.get(DATE_TIME_ORIGINAL)
        if value is None and EXIF_IFD in exif:
            value = exif.get_ifd(EXIF_IFD).get(DATE_TIME_ORIGINAL)
        return _parse_timestamp(value)
    except Exception:
        return None  # Damaged metadata must not discard a readable preview.


def _raw_timestamp(path: Path) -> Optional[datetime]:
    try:
        with _decoder_lock, path.open("rb") as stream:
            diagnostic_filter = _ExifDiagnosticFilter()
            exifread.logger.addFilter(diagnostic_filter)
            try:
                tags = exifread.process_file(stream, stop_tag="DateTimeOriginal", details=False)
            finally:
                exifread.logger.removeFilter(diagnostic_filter)
        return _parse_timestamp(tags.get("EXIF DateTimeOriginal"))
    except Exception:
        return None


def _jpeg_end(data: mmap.mmap, start: int) -> int:
    """Skip JPEG metadata segments so an EXIF thumbnail's EOI is not ours."""
    position = start + 2
    while position < len(data):
        if data[position] != 0xFF:
            return -1
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            return -1
        marker = data[position]
        position += 1
        if marker == 0xD9:
            return position - 2
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if marker in (0x00, 0xD8) or position + 2 > len(data):
            return -1
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            return -1
        position += length
        if marker == 0xDA:  # Start of scan: entropy bytes follow the header.
            return data.find(b"\xff\xd9", position)
    return -1


def _fallback_preview(path: Path) -> Optional[Image.Image]:
    """Try Pillow/TIFF previews, then validated JPEGs inside the RAW container."""
    try:
        with Image.open(path) as opened:
            # TIFF/DNG JPEGInterchangeFormat and JPEGInterchangeFormatLength.
            tags = getattr(opened, "tag_v2", {})
            offset, length = tags.get(513), tags.get(514)
            if isinstance(offset, int) and isinstance(length, int) and offset >= 0 and length > 0:
                with path.open("rb") as stream:
                    stream.seek(offset)
                    with Image.open(BytesIO(stream.read(length))) as preview:
                        return ImageOps.exif_transpose(preview).convert("RGB")
            # Never interpret a TIFF CFA sensor plane as a display preview.
            if opened.mode in ("RGB", "RGBA", "L") and tags.get(262) != 32803:
                return ImageOps.exif_transpose(opened).convert("RGB")
    except Exception:
        pass

    best = None
    try:
        with path.open("rb") as stream:
            if os.fstat(stream.fileno()).st_size == 0:
                return None
            # Map the file instead of copying an entire large RAW into memory.
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                position = 0
                while True:
                    start = data.find(b"\xff\xd8", position)
                    if start < 0:
                        break
                    position = start + 2
                    end = _jpeg_end(data, start)
                    if end < 0:
                        continue
                    try:
                        with Image.open(BytesIO(data[start:end + 2])) as candidate:
                            if candidate.format != "JPEG":
                                continue
                            candidate.load()  # Reject marker pairs containing invalid data.
                            if best is None or candidate.width * candidate.height > best.width * best.height:
                                image = ImageOps.exif_transpose(candidate).convert("RGB")
                                if best is not None:
                                    best.close()
                                best = image
                    except Exception:
                        continue
    except Exception:
        pass
    return best


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
) -> Optional[Tuple[Path, Optional[datetime]]]:
    """Return a cached JPEG and EXIF capture time (None if absent/invalid).

    The requested built-in hash naming scheme is process-specific: Python may
    choose a different filename after restart. Cache entries older than the RAW
    source are regenerated. Unsupported or damaged RAWs without a usable
    preview log a warning and return None so a batch can continue.
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

    image = None
    try:
        with _quiet_libraw(), rawpy.imread(str(raw_path)) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format != rawpy.ThumbFormat.JPEG:
                    raise ValueError("Embedded thumbnail is not JPEG")
                with Image.open(BytesIO(thumb.data)) as embedded:
                    timestamp = timestamp or _image_timestamp(embedded)
                    image = ImageOps.exif_transpose(embedded).convert("RGB")
            except Exception:
                image = _fallback_preview(raw_path)
                if image is None:
                    image = _render_preview(raw)
    except Exception:
        if image is not None:
            image.close()
        image = _fallback_preview(raw_path)
    if image is None:
        logger.warning("Skipping RAW file without a readable preview: %s", raw_path)
        return None
    timestamp = timestamp or _image_timestamp(image)

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
