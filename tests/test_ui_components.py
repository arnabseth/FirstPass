"""Exercise native culling widgets and shortcuts without a display server."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.core.clusterer import PhotoItem
from src.ui.main_window import MainWindow
from src.ui.theme import BORDER_ACTIVE, BORDER_DEFAULT, BORDER_REJECT


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    preview = tmp_path / "preview.png"
    image = QImage(400, 200, QImage.Format.Format_RGB32)
    image.fill(QColor("gray"))
    assert image.save(str(preview))
    items = [PhotoItem(
        raw_path=tmp_path / f"frame_{i}.ARW", preview_path=preview,
        timestamp=datetime(2026, 10, 2), sharpness=421.5 + i,
        phash=None, cluster_id=i // 2,
    ) for i in range(4)]
    widget = MainWindow()
    widget.populate_clusters([items[:2], [], items[2:]])
    widget.show()
    widget.activateWindow()
    widget.setFocus()
    app.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def press(window, key):
    QTest.keyClick(window, key)
    QApplication.processEvents()


def border_color(card):
    # Read Qt's resolved QSS border rather than only inspecting selector text.
    image = card.grab().toImage()
    return image.pixelColor(image.width() // 2, 1).name().upper()


def test_layout_thumbnail_and_initial_selection(window):
    assert window.cluster_rows[0].header.text() == "Cluster #0 (2 frames)"
    assert window.cluster_rows[1].header.text() == "Cluster #1 (2 frames)"
    assert window.cards[0].sharpness_badge.text() == "S: 421.5"
    assert window.current_card is window.cards[0]
    assert window.cards[0].property("selected") is True
    assert border_color(window.cards[0]) == BORDER_ACTIVE
    assert border_color(window.cards[1]) == BORDER_DEFAULT
    thumbnail = window.cards[0].thumbnail.pixmap()
    assert thumbnail.width() == 2 * thumbnail.height()
    assert thumbnail.width() <= window.cards[0].thumbnail.width()
    assert window.stats_label.text() == "Total: 4 | Picks: 0 | Rejects: 0"


def test_keyboard_navigation_across_clusters_and_boundaries(window):
    press(window, Qt.Key.Key_Left)
    assert window.active_index == 0
    press(window, Qt.Key.Key_Right)
    assert window.active_index == 1
    assert window.cards[0].property("selected") is False
    press(window, Qt.Key.Key_Right)
    assert window.current_card is window.cluster_rows[1].cards[0]
    press(window, Qt.Key.Key_Left)
    assert window.current_card is window.cluster_rows[0].cards[-1]
    for _ in range(5):
        press(window, Qt.Key.Key_Right)
    assert window.active_index == 3


def test_space_pick_delete_reject_and_css(window):
    card = window.current_card
    press(window, Qt.Key.Key_Space)
    assert card.item.is_pick and not card.item.is_reject
    assert card.property("picked") is True
    assert card.property("rejected") is False
    assert card.pick_indicator.isVisible()
    assert not card.reject_indicator.isVisible()
    assert border_color(card) == BORDER_ACTIVE
    assert window.stats_label.text() == "Total: 4 | Picks: 1 | Rejects: 0"
    press(window, Qt.Key.Key_Delete)
    assert card.item.is_reject and not card.item.is_pick
    assert card.property("picked") is False
    assert card.property("rejected") is True
    assert not card.pick_indicator.isVisible()
    assert card.reject_indicator.isVisible()
    assert border_color(card) == BORDER_REJECT
    assert window.stats_label.text() == "Total: 4 | Picks: 0 | Rejects: 1"
    assert window.purge_button.isEnabled()
    press(window, Qt.Key.Key_Space)
    assert card.item.is_pick and not card.item.is_reject
    assert border_color(card) == BORDER_ACTIVE


def test_toggle_shortcuts_and_backspace(window):
    card = window.current_card
    for key, flag in ((Qt.Key.Key_1, "is_pick"), (Qt.Key.Key_5, "is_reject")):
        press(window, key)
        assert getattr(card.item, flag)
        press(window, key)
        assert not card.item.is_pick and not card.item.is_reject
    press(window, Qt.Key.Key_Backspace)
    assert card.item.is_reject
    press(window, Qt.Key.Key_1)
    assert card.item.is_pick and not card.item.is_reject
    press(window, Qt.Key.Key_5)
    assert card.item.is_reject and not card.item.is_pick


def test_mouse_selection_and_button_focus_shortcuts(window):
    QTest.mouseClick(window.cards[2].thumbnail, Qt.MouseButton.LeftButton)
    assert window.current_card is window.cards[2]
    window.open_folder_button.setFocus()
    QTest.keyClick(window.open_folder_button, Qt.Key.Key_Space)
    QApplication.processEvents()
    assert window.cards[2].item.is_pick


def test_repopulate_empty_and_missing_preview(window, tmp_path):
    window.populate_clusters([])
    for key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Space, Qt.Key.Key_Delete):
        press(window, key)
    assert window.current_card is None
    assert not window.cards and not window.cluster_rows
    assert window.stats_label.text() == "Total: 0 | Picks: 0 | Rejects: 0"
    assert not window.purge_button.isEnabled()
    item = PhotoItem(tmp_path / "missing.ARW", tmp_path / "missing.jpg",
                     datetime(2026, 10, 2), 0.0, None, 7, is_reject=True)
    window.populate_clusters([[item]])
    QApplication.processEvents()
    assert window.current_card.thumbnail.text() == "Preview unavailable"
    assert window.current_card.property("rejected") is True
    assert window.cluster_rows[0].header.text() == "Cluster #7 (1 frames)"


def test_header_workflow_signals(window, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    folders, purges = [], []
    window.folder_selected.connect(folders.append)
    window.purge_requested.connect(purges.append)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "C:/photos")
    window.open_folder_button.click()
    assert folders == ["C:/photos"]
    assert window.scan_status_label.text() == "Folder selected: C:/photos"
    press(window, Qt.Key.Key_Delete)
    window.purge_button.click()
    assert purges == [[window.current_card.item]]
