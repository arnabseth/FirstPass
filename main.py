"""FirstPass desktop entry point."""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.theme import DARK_STYLESHEET


def main():
    # Qt 6 enables high-DPI scaling and high-DPI pixmaps automatically.
    # Keep compatibility with bindings exposing the legacy attributes.
    for name in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        attribute = getattr(Qt.ApplicationAttribute, name, None)
        if attribute is not None:
            QApplication.setAttribute(attribute)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("FirstPass")
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
