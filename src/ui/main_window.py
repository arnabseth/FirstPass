"""Keyboard-first review interface with asynchronous RAW analysis."""

from collections import deque
from time import monotonic

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QMessageBox, QProgressBar, QScrollArea, QVBoxLayout, QWidget,
)

from src.core.clusterer import PhotoItem
from src.core.file_ops import PurgeError, purge_rejects
from src.ui.components import ClusterRow, require_gui_thread
from src.ui.theme import DARK_STYLESHEET
from src.workers.cull_worker import CullWorker


class MainWindow(QMainWindow):
    folder_selected = pyqtSignal(str)
    purge_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FirstPass")
        self.resize(1100, 760)
        self.setStyleSheet(DARK_STYLESHEET)
        self.cluster_rows = []
        self.cards = []
        self.active_index = -1
        self.worker = None
        self.scanning = False
        self._close_pending = False
        self._scan_cancelled = False
        self._thread_stopped = False
        self._pending_clusters = deque()
        self._building_row = None
        self._cluster_ids = set()
        self.population_timer = QTimer(self)
        self.population_timer.setInterval(1)
        self.population_timer.timeout.connect(self._populate_batch)
        self.folder_selected.connect(self.start_scan)
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        header = QFrame()
        header.setObjectName("headerBar")
        bar = QHBoxLayout(header)
        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.clicked.connect(self.open_folder)
        self.scan_status_label = QLabel("Open a folder to start reviewing")
        self.scan_status_label.setObjectName("scanStatus")
        self.stats_label = QLabel()
        self.purge_button = QPushButton("Purge Rejects")
        self.purge_button.setObjectName("purgeButton")
        self.purge_button.clicked.connect(self.request_purge)
        for widget in (self.open_folder_button, self.scan_status_label):
            bar.addWidget(widget)
        bar.addStretch()
        bar.addWidget(self.stats_label)
        bar.addWidget(self.purge_button)
        layout.addWidget(header)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.content = QWidget()
        self.cluster_layout = QVBoxLayout(self.content)
        self.cluster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.content)
        layout.addWidget(self.scroll_area)
        self.shortcuts = []
        bindings = {
            "Left": lambda: self.move_selection(-1),
            "Right": lambda: self.move_selection(1),
            "Space": lambda: self.set_current_state("pick"),
            "Delete": lambda: self.set_current_state("reject"),
            "Backspace": lambda: self.set_current_state("reject"),
            "1": lambda: self.set_current_state("pick", toggle=True),
            "5": lambda: self.set_current_state("reject", toggle=True),
            "Esc": self.cancel_scan,
            "Shift+Delete": self.request_purge,
        }
        for key, callback in bindings.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        self.update_stats()

    @property
    def current_card(self):
        return self.cards[self.active_index] if self.active_index >= 0 else None

    def populate_clusters(self, clusters: list[list[PhotoItem]]):
        require_gui_thread()
        self.population_timer.stop()
        self._pending_clusters.clear()
        self._building_row = None
        self._cluster_ids.clear()
        while self.cluster_layout.count():
            widget = self.cluster_layout.takeAt(0).widget()
            if widget is not None:
                # Release pixmaps immediately; QObject deletion is deferred safely.
                for card in widget.cards:
                    card.thumbnail.clear()
                    card.thumbnail.source_pixmap = type(card.thumbnail.source_pixmap)()
                widget.hide()
                widget.deleteLater()
        self.cluster_rows = []
        self.cards = []
        self.active_index = -1
        for cluster in clusters:
            self.append_cluster(cluster)
        # Preserve immediate small-population behavior while bounding large work.
        self._populate_batch()
        if sum(len(cluster) for cluster in clusters) <= 24:
            while self.populating:
                self._populate_batch()

    @pyqtSlot(list)
    def append_cluster(self, cluster):
        require_gui_thread()
        if not cluster or self._scan_cancelled or self._close_pending:
            return
        cluster_id = cluster[0].cluster_id
        if cluster_id in self._cluster_ids:
            return
        self._cluster_ids.add(cluster_id)
        self._pending_clusters.append(cluster)
        self.population_timer.start()
        self.open_folder_button.setEnabled(False)
        self.update_stats()

    @property
    def populating(self):
        return bool(self._pending_clusters or self._building_row is not None)

    @pyqtSlot()
    def _populate_batch(self):
        require_gui_thread()
        deadline = monotonic() + 0.012
        for _ in range(24):
            if self._building_row is None:
                if not self._pending_clusters:
                    break
                cluster = self._pending_clusters.popleft()
                row = ClusterRow(cluster[0].cluster_id, [], self.content, frame_count=len(cluster))
                self.cluster_rows.append(row)
                self.cluster_layout.addWidget(row)
                self._building_row = (row, cluster, 0)
            row, cluster, index = self._building_row
            card = row.append_item(cluster[index])
            card.clicked.connect(self.select_card)
            self.cards.append(card)
            index += 1
            self._building_row = (row, cluster, index) if index < len(cluster) else None
            if monotonic() >= deadline:
                break
        if self.active_index < 0:
            self.select_index(0)
        if not self.populating:
            self.population_timer.stop()
            self.scan_status_label.setText(
                f"Ready — {len(self.cluster_rows)} clusters" if self.cards else "No photos to review"
            )
            if self._thread_stopped and self.worker is not None:
                self._finish_scan()
            elif not self.scanning:
                self.open_folder_button.setEnabled(True)
        else:
            self.scan_status_label.setText(f"Loading previews — {len(self.cards)} frames")
        self.update_stats()

    def start_scan(self, folder):
        if self.worker is not None or self.populating:
            return
        self._scan_cancelled = False
        self.populate_clusters([])
        self.scanning = True
        self._thread_stopped = False
        self.open_folder_button.setEnabled(False)
        self.update_stats()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.scan_status_label.setText("Scanning RAW files...")
        self.worker = CullWorker(folder, self)
        self.worker.progress.connect(self.on_progress, Qt.ConnectionType.QueuedConnection)
        self.worker.cluster_ready.connect(self.append_cluster, Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self.on_scan_result, Qt.ConnectionType.QueuedConnection)
        self.worker.error.connect(self.on_scan_error, Qt.ConnectionType.QueuedConnection)
        # CullWorker.finished(list) is the result signal; use the base signal
        # for lifetime management, including errors and interruption.
        QThread.finished.__get__(self.worker, CullWorker).connect(
            self.on_scan_stopped, Qt.ConnectionType.QueuedConnection)
        self.worker.start()

    @pyqtSlot(int, int, str)
    def on_progress(self, current, total, message):
        if not self.scanning or self._scan_cancelled:
            return
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.scan_status_label.setText(message)

    @pyqtSlot(list)
    def on_scan_result(self, clusters):
        if self._scan_cancelled or self._close_pending:
            return
        # Also support completion-only producers; streamed clusters are deduped.
        for cluster in clusters:
            self.append_cluster(cluster)
        if not self.populating:
            self.scan_status_label.setText(
                f"Ready — {len(clusters)} clusters" if clusters else "No photos to review"
            )

    @pyqtSlot(str)
    def on_scan_error(self, message):
        self.populate_clusters([])
        self.scan_status_label.setText("Scan failed")
        if not self._close_pending:
            QMessageBox.warning(self, "Scan failed", message)

    @pyqtSlot()
    def on_scan_stopped(self):
        self._thread_stopped = True
        if self._scan_cancelled:
            self.populate_clusters([])
        if not self.populating and self.worker is not None:
            self._finish_scan()

    def _finish_scan(self):
        self.scanning = False
        self.progress_bar.hide()
        self.open_folder_button.setEnabled(True)
        if self._scan_cancelled:
            self.scan_status_label.setText("Scan cancelled")
        self.worker.deleteLater()
        self.worker = None
        self.update_stats()
        if self._close_pending:
            self.close()

    def cancel_scan(self):
        if self.worker is not None:
            self._scan_cancelled = True
            self.worker.requestInterruption()
            # The thread may already have stopped while cards are still queued.
            # Clear pending UI work now; no second stopped signal will arrive.
            self.populate_clusters([])

    def closeEvent(self, event):
        if self.worker is not None:
            self._close_pending = True
            self.cancel_scan()
            event.ignore()
        else:
            self.population_timer.stop()
            self._pending_clusters.clear()
            self._building_row = None
            super().closeEvent(event)

    def select_card(self, card):
        self.select_index(self.cards.index(card))

    def select_index(self, index):
        if not self.cards:
            return
        if self.current_card is not None:
            self.current_card.set_selected(False)
        self.active_index = max(0, min(index, len(self.cards) - 1))
        self.current_card.set_selected(True)
        self.scroll_area.ensureWidgetVisible(self.current_card)

    def move_selection(self, delta):
        self.select_index(self.active_index + delta)

    def set_current_state(self, state, toggle=False):
        if self.scanning or self.populating:
            return
        card = self.current_card
        if card is None:
            return
        item = card.item
        if state == "pick":
            item.is_pick = not item.is_pick if toggle else True
            item.is_reject = False
        else:
            item.is_reject = not item.is_reject if toggle else True
            item.is_pick = False
        card.refresh_state()
        self.update_stats()

    def update_stats(self):
        picks = sum(card.item.is_pick for card in self.cards)
        rejects = sum(card.item.is_reject for card in self.cards)
        self.stats_label.setText(f"Total: {len(self.cards)} | Picks: {picks} | Rejects: {rejects}")
        self.purge_button.setEnabled(rejects > 0 and not self.scanning and not self.populating)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Photo Folder")
        if folder:
            self.scan_status_label.setText(f"Folder selected: {folder}")
            self.folder_selected.emit(folder)

    def request_purge(self):
        if self.scanning or self.populating:
            return
        rejects = [card.item for card in self.cards if card.item.is_reject]
        if rejects:
            self.purge_requested.emit(rejects)
            answer = QMessageBox.question(
                self, "Purge Rejects",
                f"Send {len(rejects)} rejected RAW files to Recycle Bin / Trash?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            error = None
            try:
                count, paths = purge_rejects([card.item for card in self.cards])
            except PurgeError as exc:
                paths = exc.trashed_paths
                count, error = len(paths), str(exc)
            clusters = [[card.item for card in row.cards if card.item.raw_path not in paths]
                        for row in self.cluster_rows]
            self.populate_clusters(clusters)
            self.scan_status_label.setText(f"Sent {count} rejected RAW files to Trash")
            if error:
                QMessageBox.warning(self, "Purge incomplete", error)
