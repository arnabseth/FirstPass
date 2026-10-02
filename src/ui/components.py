"""Photo cards and horizontal burst survey rows."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.core.clusterer import PhotoItem


class ThumbnailLabel(QLabel):
    """Rescale the original preview whenever the display area changes."""

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.source_pixmap = QPixmap(str(path))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 150)
        self.setFixedHeight(180)
        self.update_thumbnail()

    def update_thumbnail(self):
        if self.source_pixmap.isNull():
            self.setText("Preview unavailable")
        else:
            self.setPixmap(self.source_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_thumbnail()


class PhotoCard(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, item: PhotoItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.selected = False
        self.setObjectName("photoCard")
        self.setFixedWidth(260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.thumbnail = ThumbnailLabel(item.preview_path, self)
        layout.addWidget(self.thumbnail)
        self.filename_label = QLabel(item.raw_path.name)
        self.filename_label.setObjectName("filename")
        self.filename_label.setToolTip(str(item.raw_path))
        layout.addWidget(self.filename_label)
        badges = QHBoxLayout()
        self.sharpness_badge = QLabel()
        self.sharpness_badge.setObjectName("sharpnessBadge")
        self.pick_indicator = QLabel("PICK")
        self.pick_indicator.setObjectName("pickIndicator")
        self.reject_indicator = QLabel("REJECT")
        self.reject_indicator.setObjectName("rejectIndicator")
        for label in (self.sharpness_badge, self.pick_indicator, self.reject_indicator):
            badges.addWidget(label)
        badges.addStretch()
        layout.addLayout(badges)
        self.refresh_state()

    def set_selected(self, selected: bool):
        self.selected = selected
        self.refresh_state()

    def refresh_state(self):
        self.setProperty("selected", self.selected)
        self.setProperty("picked", self.item.is_pick)
        self.setProperty("rejected", self.item.is_reject)
        self.sharpness_badge.setText(f"S: {self.item.sharpness:.1f}")
        self.pick_indicator.setVisible(self.item.is_pick)
        self.reject_indicator.setVisible(self.item.is_reject)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)


class ClusterRow(QWidget):
    def __init__(self, cluster_id: int, items: list[PhotoItem], parent=None):
        super().__init__(parent)
        self.cluster_id = cluster_id
        layout = QVBoxLayout(self)
        self.header = QLabel(f"Cluster #{cluster_id} ({len(items)} frames)")
        self.header.setObjectName("clusterHeader")
        layout.addWidget(self.header)
        row = QHBoxLayout()
        self.cards = [PhotoCard(item, self) for item in items]
        for card in self.cards:
            row.addWidget(card)
        row.addStretch()
        layout.addLayout(row)
