"""Keyboard-first review interface with asynchronous RAW analysis."""

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QMessageBox, QProgressBar, QScrollArea, QVBoxLayout, QWidget,
)

from src.core.clusterer import PhotoItem
from src.core.file_ops import PurgeError, purge_rejects
from src.ui.components import ClusterRow
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
        while self.cluster_layout.count():
            widget = self.cluster_layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.cluster_rows = []
        self.cards = []
        self.active_index = -1
        for cluster in clusters:
            self.append_cluster(cluster)
        if self.cards:
            self.select_index(0)
        self.scan_status_label.setText(
            f"Ready — {len(self.cluster_rows)} clusters" if self.cards else "No photos to review"
        )
        self.update_stats()

    def append_cluster(self, cluster):
        if not cluster:
            return
        row = ClusterRow(cluster[0].cluster_id, cluster, self.content)
        self.cluster_rows.append(row)
        self.cluster_layout.addWidget(row)
        for card in row.cards:
            card.clicked.connect(self.select_card)
            self.cards.append(card)
        if self.active_index < 0:
            self.select_index(0)
        self.update_stats()

    def start_scan(self, folder):
        if self.worker is not None and self.worker.isRunning():
            return
        self.populate_clusters([])
        self.scanning = True
        self._scan_cancelled = False
        self.open_folder_button.setEnabled(False)
        self.update_stats()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.scan_status_label.setText("Scanning RAW files...")
        self.worker = CullWorker(folder, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.cluster_ready.connect(self.append_cluster)
        self.worker.finished.connect(self.on_scan_result)
        self.worker.error.connect(self.on_scan_error)
        # CullWorker.finished(list) is the result signal; use the base signal
        # for lifetime management, including errors and interruption.
        QThread.finished.__get__(self.worker, CullWorker).connect(self.on_scan_stopped)
        self.worker.start()

    def on_progress(self, current, total, message):
        if not self.scanning or self._scan_cancelled:
            return
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.scan_status_label.setText(message)

    def on_scan_result(self, clusters):
        self.scan_status_label.setText(
            f"Ready — {len(clusters)} clusters" if clusters else "No photos to review"
        )

    def on_scan_error(self, message):
        self.populate_clusters([])
        self.scan_status_label.setText("Scan failed")
        if not self._close_pending:
            QMessageBox.warning(self, "Scan failed", message)

    def on_scan_stopped(self):
        self.scanning = False
        self.progress_bar.hide()
        self.open_folder_button.setEnabled(True)
        if self._scan_cancelled:
            self.populate_clusters([])
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

    def closeEvent(self, event):
        if self.worker is not None:
            self._close_pending = True
            self.cancel_scan()
            event.ignore()
        else:
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
        if self.scanning:
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
        self.purge_button.setEnabled(rejects > 0 and not self.scanning)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Photo Folder")
        if folder:
            self.scan_status_label.setText(f"Folder selected: {folder}")
            self.folder_selected.emit(folder)

    def request_purge(self):
        if self.scanning:
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
