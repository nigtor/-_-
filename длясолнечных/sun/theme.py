"""Цвета и QSS. Не импортирует sun.*"""
BG_DEEP   = "#0a0705"
BG        = "#0f0b08"
PANEL     = "#151009"
PANEL_HI  = "#1c150c"
BORDER    = "#2a2015"
BORDER_HI = "#3d2f1c"
ACCENT    = "#d97706"
ACCENT_HI = "#f59e0b"
ACCENT_LO = "#92400e"
TEXT      = "#e8dfd0"
DIM       = "#8a7a63"
OK        = "#4ade80"
WARN      = "#fbbf24"
ERR       = "#f87171"

QSS = f"""
QWidget {{
    color: {TEXT};
    font-family: 'JetBrains Mono','Cascadia Mono','Consolas','DejaVu Sans Mono',monospace;
    font-size: 12px;
}}
QMainWindow {{ background: {BG_DEEP}; }}
#clear {{ background: transparent; }}
#titlebar {{ background: {BG_DEEP}; border-bottom: 1px solid {BORDER}; }}
#logo {{ font-size: 15px; font-weight: 800; color: #fff5e6; letter-spacing: 4px; }}
#sub {{ font-size: 10px; color: {DIM}; letter-spacing: 3px; padding-top: 3px; }}
#sidebar {{ background: {BG}; border-right: 1px solid {BORDER}; }}
#accbox {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px;
}}
#accname {{ color: {ACCENT_HI}; font-weight: 700; font-size: 13px; }}
#tiny {{ color: {DIM}; font-size: 9px; letter-spacing: 2px; font-weight: 700; }}
#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
#hero {{ background: {PANEL_HI}; border: 1px solid {BORDER_HI}; border-radius: 12px; }}
#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
#cardname {{ font-size: 14px; font-weight: 700; color: #f5ecdd; }}
#h1 {{ font-size: 21px; font-weight: 800; color: #fff5e6; }}
#muted {{ color: {DIM}; }}
#accent {{ color: {ACCENT_HI}; font-weight: 700; }}
#avatar {{ background: #120c06; border: 1px solid {BORDER}; border-radius: 8px; }}
QPushButton#nav {{
    text-align: left; padding: 10px 12px; color: {DIM};
    background: transparent; border: 1px solid transparent; border-radius: 7px;
    font-size: 11px; letter-spacing: 1px;
}}
QPushButton#nav:hover {{ background: {PANEL}; color: {TEXT}; border-color: {BORDER}; }}
QPushButton#nav:checked {{
    background: {PANEL_HI}; color: #fff5e6;
    border: 1px solid {ACCENT_LO}; border-left: 3px solid {ACCENT_HI};
}}
QPushButton#win {{
    color: {DIM}; background: transparent; border: none; border-radius: 6px; font-size: 13px;
}}
QPushButton#win:hover {{ background: {PANEL_HI}; color: #fff5e6; }}
QLineEdit, QComboBox, QPlainTextEdit {{
    background: {BG_DEEP}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 8px 10px; selection-background-color: {ACCENT}; color: {TEXT};
}}
QLineEdit:hover, QComboBox:hover, QPlainTextEdit:hover {{ border-color: {BORDER_HI}; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: #4a3f30; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {DIM}; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL}; border: 1px solid {BORDER_HI}; border-radius: 8px;
    selection-background-color: {ACCENT}; selection-color: #1a1206;
    outline: none; padding: 4px;
}}
QListWidget#list, QTreeWidget#tree {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 9px; outline: none;
}}
QListWidget#list::item {{
    padding: 9px 10px; color: #c4b8a4; border-bottom: 1px solid #14100a;
    border-radius: 6px; margin: 1px 3px;
}}
QListWidget#list::item:hover {{ background: {PANEL}; color: {TEXT}; }}
QListWidget#list::item:selected {{
    background: {PANEL_HI}; color: #fff5e6; border-left: 2px solid {ACCENT_HI};
}}
QListWidget#list::item:disabled {{ color: #4a3f30; }}
QTreeWidget#tree::item {{ padding: 7px 5px; color: #c4b8a4; border-radius: 6px; }}
QTreeWidget#tree::item:hover {{ background: {PANEL}; }}
QTreeWidget#tree::item:selected {{ background: {PANEL_HI}; color: #fff5e6; }}
QHeaderView::section {{
    background: {PANEL}; color: {DIM}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 8px 6px; font-size: 10px;
    letter-spacing: 1px; font-weight: 700;
}}
QScrollArea#scroll {{ background: transparent; border: none; }}
QScrollArea#scroll > QWidget > QWidget {{ background: transparent; }}
QSlider::groove:horizontal {{
    height: 5px; background: {BG_DEEP}; border: 1px solid {BORDER}; border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 14px; height: 18px; margin: -7px 0; border-radius: 4px;
    background: {ACCENT_HI}; border: 1px solid {BG_DEEP};
}}
QSlider::handle:horizontal:hover {{ background: #ffcf6b; }}
QCheckBox {{ spacing: 8px; color: #c4b8a4; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border: 1px solid {BORDER_HI}; border-radius: 4px;
    background: {BG_DEEP};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT_HI}; }}
QScrollBar:vertical {{ background: transparent; width: 11px; border: none; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {BORDER_HI}; min-height: 30px; border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QMenu {{
    background: {PANEL}; border: 1px solid {BORDER_HI}; border-radius: 9px; padding: 5px;
}}
QMenu::item {{ padding: 7px 20px 7px 12px; color: {TEXT}; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: #1a1206; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
QToolTip {{
    background: {PANEL_HI}; color: {TEXT}; border: 1px solid {BORDER_HI};
    border-radius: 6px; padding: 5px 8px;
}}
QMessageBox {{ background: {PANEL}; }}
QProgressBar {{ border-radius: 3px; }}
"""