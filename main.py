"""FirstPass desktop entry point."""

import faulthandler
import os
import sys
import traceback

_fault_stream = None


def report_unhandled_exception(exception_type, exception, traceback_object):
    """Keep exceptions escaping Qt callbacks visible instead of disappearing."""
    traceback.print_exception(exception_type, exception, traceback_object, file=sys.stderr)
    sys.stderr.flush()


def install_crash_diagnostics():
    global _fault_stream
    sys.excepthook = report_unhandled_exception
    if _fault_stream is None:
        # Keep this descriptor open for the lifetime of faulthandler. LibRaw's
        # temporary fd-2 redirect must not swallow native crash stack traces.
        _fault_stream = os.fdopen(os.dup(sys.stderr.fileno()), "wb", buffering=0)
    faulthandler.enable(file=_fault_stream, all_threads=True)


def main():
    install_crash_diagnostics()
    # Enable diagnostics before importing or initializing native Qt code.
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication
    from src.ui.main_window import MainWindow
    from src.ui.theme import DARK_STYLESHEET

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
