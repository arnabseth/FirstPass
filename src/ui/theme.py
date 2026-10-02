"""Dark interface tokens and Qt stylesheet."""

WINDOW_CANVAS = "#121214"
CARD_SURFACE = "#1A1A1E"
BORDER_DEFAULT = "#2A2A30"
BORDER_ACTIVE = "#00E599"
BORDER_REJECT = "#FF4B4B"
TEXT_PRIMARY = "#EDEDED"
TEXT_MUTED = "#8E8E93"

DARK_STYLESHEET = f"""
QWidget {{ background-color: {WINDOW_CANVAS}; color: {TEXT_PRIMARY};
           font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
QFrame#headerBar {{ border-bottom: 1px solid {BORDER_DEFAULT}; }}
QFrame#photoCard {{ background-color: {CARD_SURFACE};
                   border: 2px solid {BORDER_DEFAULT}; border-radius: 8px; }}
QFrame#photoCard[picked="true"] {{ border-color: {BORDER_ACTIVE}; }}
QFrame#photoCard[selected="true"] {{ border-color: {BORDER_ACTIVE}; }}
QFrame#photoCard[rejected="true"] {{ border-color: {BORDER_REJECT}; }}
QFrame#photoCard[selected="true"] {{ border-width: 3px; }}
QFrame#photoCard QLabel {{ background: transparent; border: none; }}
QLabel#sharpnessBadge, QLabel#filename, QLabel#scanStatus {{ color: {TEXT_MUTED}; }}
QLabel#pickIndicator {{ color: {BORDER_ACTIVE}; font-weight: bold; }}
QLabel#rejectIndicator {{ color: {BORDER_REJECT}; font-weight: bold; }}
QLabel#clusterHeader {{ font-size: 15px; font-weight: bold; }}
QPushButton {{ background-color: {CARD_SURFACE}; border: 1px solid {BORDER_DEFAULT};
               border-radius: 6px; padding: 8px 14px; }}
QPushButton:hover, QPushButton:focus {{ border-color: {BORDER_ACTIVE}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; }}
QPushButton#purgeButton {{ color: {BORDER_REJECT}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: {WINDOW_CANVAS}; width: 12px; }}
QScrollBar:horizontal {{ background: {WINDOW_CANVAS}; height: 12px; }}
QScrollBar::handle {{ background: {BORDER_DEFAULT}; border-radius: 5px;
                      min-width: 24px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
"""
