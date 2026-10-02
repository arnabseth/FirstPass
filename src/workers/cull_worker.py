"""Run the RAW analysis pipeline outside the GUI thread."""

import hashlib
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.analyzer import calculate_sharpness, compute_phash
from src.core.clusterer import PhotoItem, group_and_rank_bursts
from src.core.extractor import extract_embedded_jpeg
from src.core.scanner import scan_directory


class CullWorker(QThread):
    progress = pyqtSignal(int, int, str)
    cluster_ready = pyqtSignal(list)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.directory = Path(directory)
        self.cache_dir = Path(tempfile.gettempdir()) / "firstpass-previews"

    def run(self):
        # Thread boundary: emit only PhotoItem dataclasses with preview Paths.
        # QImage, QPixmap and all widgets belong exclusively to the GUI thread.
        try:
            self.progress.emit(0, 0, "Scanning RAW files...")
            paths = scan_directory(self.directory)
            total = len(paths) * 2 + 1
            items = []
            for index, path in enumerate(paths):
                if self.isInterruptionRequested():
                    return
                self.progress.emit(index * 2, total, f"Extracting preview: {path.name}")
                # The extractor names entries by basename; isolate source folders.
                key = hashlib.sha256(str(path.parent.resolve()).encode()).hexdigest()
                extracted = extract_embedded_jpeg(path, self.cache_dir / key)
                if extracted is None:
                    self.progress.emit(index * 2 + 1, total, f"Skipping unreadable frame: {path.name}")
                    continue
                preview, timestamp = extracted
                self.progress.emit(index * 2 + 1, total, f"Evaluating sharpness: {path.name}")
                # Unknown capture times must not produce automatic burst rejects.
                timestamp = timestamp or datetime.min + timedelta(days=index + 1)
                items.append(PhotoItem(path, preview, timestamp,
                                       calculate_sharpness(preview), compute_phash(preview), -1))
            if self.isInterruptionRequested():
                return
            self.progress.emit(total - 1, total, "Grouping and ranking bursts...")
            clusters = group_and_rank_bursts(items)
            for cluster in clusters:
                if self.isInterruptionRequested():
                    return
                self.cluster_ready.emit(cluster)
            self.progress.emit(total, total, "Analysis complete")
            self.finished.emit(clusters)
        except Exception as exc:
            self.error.emit(str(exc))
