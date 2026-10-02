"""Large completion batches, thread boundaries and native-resource cleanup."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import ctypes
import gc
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QThread, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.core.clusterer import PhotoItem
from src.ui.components import PhotoCard
from src.ui.main_window import MainWindow
from src.workers.cull_worker import CullWorker


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_clusters(tmp_path, count=120, frames=2):
    preview = tmp_path / "large-preview.jpg"
    Image.new("RGB", (4000, 3000), "gray").save(preview)
    return [[PhotoItem(tmp_path / f"{i}-{j}.ARW", preview,
                       datetime(2026, 10, 2), float(j), None, i,
                       is_pick=j == 0, is_reject=j != 0)
             for j in range(frames)] for i in range(count)]


def wait_until(app, condition):
    for _ in range(1000):
        app.processEvents()
        if condition():
            return
        QTest.qWait(5)
    pytest.fail("UI population did not complete")


def flush_deletions(app):
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()


def gdi_handles():
    if sys.platform != "win32":
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    user.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user.GetGuiResources.restype = ctypes.c_uint
    return user.GetGuiResources(kernel.GetCurrentProcess(), 0)


def test_120_cluster_completion_bounded_responsive_and_released(app, tmp_path):
    clusters = make_clusters(tmp_path)
    window = MainWindow()
    window.show()
    app.processEvents()
    baseline = gdi_handles()
    counts = []
    heartbeat = QTimer()
    heartbeat.setInterval(1)
    heartbeat.timeout.connect(lambda: counts.append(len(window.cards)))
    heartbeat.start()
    try:
        for _ in range(3):
            # Exercise exactly the worker's result signal, including duplicate
            # streamed clusters, without loading a real camera RAW file.
            worker = CullWorker(tmp_path)
            worker.cluster_ready.connect(window.append_cluster)
            worker.finished.connect(window.on_scan_result)
            worker.cluster_ready.emit(clusters[0])
            worker.finished.emit(clusters)
            assert len(window.cards) < 240
            assert window.populating and not window.purge_button.isEnabled()
            wait_until(app, lambda: not window.populating)
            assert len(window.cluster_rows) == 120 and len(window.cards) == 240
            assert window.scroll_area.widgetResizable()
            assert window.scan_status_label.text() == "Ready — 120 clusters"
            assert window.purge_button.isEnabled()
            for card in window.cards:
                assert card.thread() == app.thread()
                pixmap = card.thumbnail.source_pixmap
                assert not pixmap.isNull()
                assert pixmap.width() <= 300 and pixmap.height() <= 200
            old_rows, old_cards = list(window.cluster_rows), list(window.cards)
            window.populate_clusters([])
            flush_deletions(app)
            assert all(sip.isdeleted(row) for row in old_rows)
            assert all(sip.isdeleted(card) for card in old_cards)
            assert not window.findChildren(PhotoCard)
            assert window.cluster_layout.count() == 0
            if baseline is not None:
                # Allow a few cached Qt/platform resources, but no accumulation
                # proportional to 240 cards across repeated completion cycles.
                assert gdi_handles() <= baseline + 10
            worker.deleteLater()
        assert any(0 < count < 240 for count in counts)
    finally:
        heartbeat.stop()
        window.close()
        window.deleteLater()
        flush_deletions(app)


def test_one_large_cluster_and_pending_replacement(app, tmp_path):
    window = MainWindow()
    clusters = make_clusters(tmp_path, count=1, frames=150)
    try:
        window.populate_clusters(clusters)
        assert len(window.cards) <= 24 and window.populating
        old_rows = list(window.cluster_rows)
        # Cancel pending cards as well as deleting already-built rows.
        replacement = make_clusters(tmp_path, count=1, frames=1)
        window.populate_clusters(replacement)
        wait_until(app, lambda: not window.populating)
        flush_deletions(app)
        assert len(window.cards) == 1 and all(sip.isdeleted(row) for row in old_rows)
        assert len(window.findChildren(PhotoCard)) == 1
    finally:
        window.close()
        window.deleteLater()
        flush_deletions(app)


def test_worker_finished_on_background_thread_renders_on_gui(app, tmp_path, monkeypatch):
    clusters = make_clusters(tmp_path, count=110, frames=1)
    creation_threads = []
    original = PhotoCard.__init__
    def record_creation(self, *args, **kwargs):
        creation_threads.append(QThread.currentThread())
        original(self, *args, **kwargs)
    monkeypatch.setattr(PhotoCard, "__init__", record_creation)
    def emit_completion(self):
        assert QThread.currentThread() != app.thread()
        self.finished.emit(clusters)
    monkeypatch.setattr(CullWorker, "run", emit_completion)
    window = MainWindow()
    window.show()
    try:
        window.start_scan(tmp_path)
        wait_until(app, lambda: window.worker is None)
        assert len(window.cards) == 110 and not window.scanning and not window.populating
        assert all(thread == app.thread() for thread in creation_threads)
        assert window.open_folder_button.isEnabled()
    finally:
        if window.worker is not None:
            window.worker.wait(5000)
        window.close()
        window.deleteLater()
        flush_deletions(app)


def test_crash_diagnostics_in_headless_subprocess():
    code = """
import faulthandler, sys
import main
main.install_crash_diagnostics()
assert faulthandler.is_enabled()
from src.core.extractor import _quiet_libraw
with _quiet_libraw():
    faulthandler.dump_traceback(file=main._fault_stream)
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
app = QApplication([])
def fail():
    raise RuntimeError('synthetic Qt callback failure')
QTimer.singleShot(0, fail)
QTimer.singleShot(20, app.quit)
app.exec()
"""
    result = subprocess.run([sys.executable, "-c", code],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "Traceback (most recent call last)" in result.stderr
    assert "RuntimeError: synthetic Qt callback failure" in result.stderr
    assert "Current thread" in result.stderr


def test_cancel_after_thread_stops_discards_pending_cards(app, tmp_path, monkeypatch):
    clusters = make_clusters(tmp_path)
    monkeypatch.setattr(CullWorker, "run", lambda self: self.finished.emit(clusters))
    window = MainWindow()
    try:
        window.start_scan(tmp_path)
        wait_until(app, lambda: window._thread_stopped)
        assert window.populating and window.worker is not None
        window.cancel_scan()
        wait_until(app, lambda: window.worker is None)
        assert not window.cards and not window.cluster_rows and not window.populating
        assert window.scan_status_label.text() == "Scan cancelled"
        assert not window.population_timer.isActive()
    finally:
        if window.worker is not None:
            window.worker.wait(5000)
        window.close()
        window.deleteLater()
        flush_deletions(app)
