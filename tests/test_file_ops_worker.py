"""Safe disposal and asynchronous pipeline integration under headless Qt."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime
from pathlib import Path
from threading import get_ident

import pytest
from PIL import Image
from PyQt6.QtCore import QThread
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core import file_ops
from src.core.clusterer import PhotoItem
from src.ui.main_window import MainWindow
from src.workers import cull_worker


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def photo(tmp_path, name="frame", reject=True):
    raw, preview = tmp_path / f"{name}.ARW", tmp_path / f"{name}.jpg"
    raw.write_bytes(b"original")
    Image.new("RGB", (32, 32), "gray").save(preview)
    return PhotoItem(raw, preview, datetime(2026, 10, 2), 1.0, None, 0,
                     is_pick=not reject, is_reject=reject)


def wait_until(app, condition):
    for _ in range(500):
        app.processEvents()
        if condition():
            return
        QTest.qWait(10)
    pytest.fail("Timed out waiting for worker signals")


def test_purge_only_rejects_and_cleanup(tmp_path, monkeypatch):
    reject, pick = photo(tmp_path), photo(tmp_path, "pick", False)
    calls = []
    monkeypatch.setattr(file_ops.send2trash, "send2trash", calls.append)
    assert file_ops.purge_rejects([reject, pick, reject]) == (1, [reject.raw_path])
    assert calls == [str(reject.raw_path)]
    assert not reject.preview_path.exists()
    assert pick.raw_path.exists() and pick.preview_path.exists()
    assert reject.raw_path.read_bytes() == b"original"  # mock trash, never unlink RAW


def test_dry_run_and_empty(tmp_path, monkeypatch):
    item = photo(tmp_path)
    monkeypatch.setattr(file_ops.send2trash, "send2trash",
                        lambda path: pytest.fail("Dry run called trash"))
    assert file_ops.purge_rejects([item], dry_run=True) == (1, [item.raw_path])
    assert item.raw_path.exists() and item.preview_path.exists()
    assert file_ops.purge_rejects([]) == (0, [])


def test_failed_trash_preserves_preview(tmp_path, monkeypatch):
    item = photo(tmp_path)
    def fail(path):
        raise OSError("Trash unavailable")
    monkeypatch.setattr(file_ops.send2trash, "send2trash", fail)
    with pytest.raises(file_ops.PurgeError) as caught:
        file_ops.purge_rejects([item])
    assert caught.value.trashed_paths == []
    assert item.raw_path.exists() and item.preview_path.exists()


def test_shared_preview_and_raw_protection(tmp_path, monkeypatch):
    item, pick = photo(tmp_path), photo(tmp_path, "pick", False)
    monkeypatch.setattr(file_ops.send2trash, "send2trash", lambda path: None)
    item.preview_path = pick.preview_path
    file_ops.purge_rejects([item, pick])
    assert pick.preview_path.exists()
    item.preview_path = item.raw_path
    file_ops.purge_rejects([item])
    assert item.raw_path.exists()


def test_partial_purge_reports_successful_paths(tmp_path, monkeypatch):
    first, second = photo(tmp_path), photo(tmp_path, "second")
    def trash(path):
        if path == str(second.raw_path):
            raise OSError("Permission denied")
    monkeypatch.setattr(file_ops.send2trash, "send2trash", trash)
    with pytest.raises(file_ops.PurgeError) as caught:
        file_ops.purge_rejects([first, second])
    assert caught.value.trashed_paths == [first.raw_path]
    assert not first.preview_path.exists()
    assert second.preview_path.exists() and second.raw_path.exists()


def mock_extractor(monkeypatch, missing_time=False):
    threads, caches = [], []
    def extract(path, cache):
        threads.append(get_ident())
        caches.append(cache)
        cache.mkdir(parents=True, exist_ok=True)
        preview = cache / f"{path.stem}.jpg"
        Image.new("RGB", (32, 32), "gray").save(preview)
        return preview, None if missing_time else datetime(2026, 10, 2)
    monkeypatch.setattr(cull_worker, "extract_embedded_jpeg", extract)
    return threads, caches


def collect_worker(app, worker):
    progress, clusters, results, errors, stopped = [], [], [], [], []
    worker.progress.connect(lambda *args: progress.append(args))
    worker.cluster_ready.connect(clusters.append)
    worker.finished.connect(results.append)
    worker.error.connect(errors.append)
    QThread.finished.__get__(worker, cull_worker.CullWorker).connect(lambda: stopped.append(True))
    worker.start()
    try:
        wait_until(app, lambda: bool(stopped))
    finally:
        worker.requestInterruption()
        assert worker.wait(5000)
    app.processEvents()
    return progress, clusters, results, errors


def test_worker_pipeline_signals_on_background_thread(app, tmp_path, monkeypatch):
    for name in ("one", "two"):
        (tmp_path / f"{name}.ARW").write_bytes(b"mock")
    threads, _ = mock_extractor(monkeypatch)
    worker = cull_worker.CullWorker(tmp_path)
    worker.cache_dir = tmp_path / "cache"
    progress, clusters, results, errors = collect_worker(app, worker)
    assert not errors
    assert results == [clusters] and len(clusters) == 1
    assert len(clusters[0]) == 2
    assert sum(item.is_pick for item in clusters[0]) == 1
    assert sum(item.is_reject for item in clusters[0]) == 1
    assert all(thread != get_ident() for thread in threads)
    assert progress[0] == (0, 0, "Scanning RAW files...")
    assert progress[-1][:2] == (5, 5)
    assert [p[0] for p in progress] == sorted(p[0] for p in progress)


def test_worker_unknown_times_and_separate_caches(app, tmp_path, monkeypatch):
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "same.ARW").write_bytes(b"mock")
    _, caches = mock_extractor(monkeypatch, missing_time=True)
    worker = cull_worker.CullWorker(tmp_path)
    worker.cache_dir = tmp_path / "cache"
    _, clusters, results, errors = collect_worker(app, worker)
    assert not errors and results
    assert len(clusters) == 2 and all(c[0].is_pick for c in clusters)
    assert len(set(caches)) == 2


def test_worker_empty_and_error(app, tmp_path):
    _, clusters, results, errors = collect_worker(app, cull_worker.CullWorker(tmp_path))
    assert clusters == [] and results == [[]] and errors == []
    _, clusters, results, errors = collect_worker(app, cull_worker.CullWorker(tmp_path / "missing"))
    assert clusters == [] and results == [] and len(errors) == 1


def test_worker_extraction_failure(app, tmp_path, monkeypatch):
    (tmp_path / "bad.ARW").write_bytes(b"invalid RAW")
    def fail(*args):
        raise ValueError("Invalid RAW")
    monkeypatch.setattr(cull_worker, "extract_embedded_jpeg", fail)
    _, clusters, results, errors = collect_worker(app, cull_worker.CullWorker(tmp_path))
    assert not clusters and not results and errors == ["Invalid RAW"]


@pytest.mark.parametrize("include_readable", [True, False])
def test_worker_skips_unreadable_frames(app, tmp_path, monkeypatch, include_readable):
    (tmp_path / "bad.ARW").write_bytes(b"invalid RAW")
    if include_readable:
        (tmp_path / "good.ARW").write_bytes(b"mock")
    mock_extractor(monkeypatch)
    extract = cull_worker.extract_embedded_jpeg
    monkeypatch.setattr(cull_worker, "extract_embedded_jpeg",
                        lambda path, cache: None if path.stem == "bad" else extract(path, cache))
    worker = cull_worker.CullWorker(tmp_path)
    worker.cache_dir = tmp_path / "cache"
    progress, clusters, results, errors = collect_worker(app, worker)
    assert not errors and results == [clusters]
    assert len(clusters) == int(include_readable)
    if include_readable:
        assert clusters[0][0].raw_path.name == "good.ARW"
    assert any("Skipping unreadable frame" in p[2] for p in progress)
    assert progress[-1][0] == progress[-1][1]


def test_close_during_scan_cancels_without_destroying_thread(app, tmp_path, monkeypatch):
    from threading import Event
    entered, release = Event(), Event()
    (tmp_path / "frame.ARW").write_bytes(b"mock")
    preview = tmp_path / "frame.jpg"
    Image.new("RGB", (32, 32), "gray").save(preview)
    def extract(*args):
        entered.set()
        assert release.wait(5)
        return preview, datetime(2026, 10, 2)
    monkeypatch.setattr(cull_worker, "extract_embedded_jpeg", extract)
    window = MainWindow()
    window.show()
    try:
        window.start_scan(tmp_path)
        wait_until(app, entered.is_set)
        window.close()
        assert window.isVisible() and window.worker.isInterruptionRequested()
        release.set()
        wait_until(app, lambda: window.worker is None)
        assert not window.isVisible() and not window.cards
        assert window.scan_status_label.text() == "Scan cancelled"
    finally:
        release.set()
        if window.worker is not None:
            window.worker.wait(5000)
            app.processEvents()
        window.close()
        window.deleteLater()
        app.processEvents()


def test_window_partial_purge_updates_only_completed_items(app, tmp_path, monkeypatch):
    first, second = photo(tmp_path), photo(tmp_path, "second")
    def trash(path):
        if path == str(second.raw_path):
            raise OSError("Permission denied")
    monkeypatch.setattr(file_ops.send2trash, "send2trash", trash)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    window = MainWindow()
    try:
        window.populate_clusters([[first, second]])
        window.request_purge()
        assert [card.item for card in window.cards] == [second]
        assert window.purge_button.isEnabled() and len(warnings) == 1
        assert window.stats_label.text() == "Total: 1 | Picks: 0 | Rejects: 1"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_window_scan_and_confirmed_purge(app, tmp_path, monkeypatch):
    for name in ("one", "two"):
        (tmp_path / f"{name}.ARW").write_bytes(b"mock")
    mock_extractor(monkeypatch)
    monkeypatch.setattr(cull_worker.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    monkeypatch.setattr("src.ui.main_window.QFileDialog.getExistingDirectory", lambda *args: str(tmp_path))
    calls, questions = [], []
    monkeypatch.setattr(file_ops.send2trash, "send2trash", calls.append)
    answer = QMessageBox.StandardButton.No
    def confirm(*args):
        questions.append(args[2])
        return answer
    monkeypatch.setattr(QMessageBox, "question", confirm)
    window = MainWindow()
    try:
        window.open_folder_button.click()
        assert window.scanning and not window.open_folder_button.isEnabled()
        assert not window.progress_bar.isHidden()
        wait_until(app, lambda: window.worker is None)
        assert len(window.cluster_rows) == 1 and len(window.cards) == 2
        assert window.progress_bar.isHidden() and window.purge_button.isEnabled()
        window.request_purge()
        assert calls == [] and len(window.cards) == 2
        answer = QMessageBox.StandardButton.Yes
        window.request_purge()
        assert questions[-1] == "Send 1 rejected RAW files to Recycle Bin / Trash?"
        assert len(calls) == 1 and len(window.cards) == 1
        assert not window.purge_button.isEnabled()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
