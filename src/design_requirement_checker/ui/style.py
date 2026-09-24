"""Centralized presentation tokens for the Qt UI.

Visual reference: ``prototype/styles.css``. This module is the single owner
of shared visual values (font families, colors, spacing) so widgets stop
hard-coding hex values. It is presentation-only: it knows nothing about the
domain, matching or persistence, and it is deliberately *not* a design-system
framework — just shared constants, a badge-styling helper and one application
stylesheet applied at startup.

Prototype → production translation rules:

- The prototype's browser look (light neutral background, white cards, blue
  primary action, subtle borders, compact professional engineering-tool
  aesthetic) is approximated with native Qt widgets plus this stylesheet.
- Windows-friendliness is a requirement: Segoe UI / Microsoft YaHei first,
  with a graceful fallback list for other platforms.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QPushButton

#: Font stack — Windows first, with macOS/Linux fallbacks (prototype :root).
FONT_FAMILIES: tuple[str, ...] = (
    "Segoe UI",
    "Microsoft YaHei",
    "PingFang SC",
    "sans-serif",
)

# --- palette (prototype :root and component colors) -----------------------

TEXT = "#243247"
MUTED = "#596779"
BACKGROUND = "#f3f5f7"
CARD = "#ffffff"
BORDER = "#d5dce4"
PANEL_TINT = "#fafbfd"
PANEL_HEADING = "#f7f9fb"

PRIMARY = "#245ba5"
PRIMARY_DARK = "#194982"
PRIMARY_LIGHT = "#e9f1fc"
PRIMARY_TINT = "#e4edf9"
SELECTED_ROW = "#eaf1fb"
FOCUS_RING = "#447ec8"

# Status semantics — colors only, never new meaning (constitution §5–§7).
CONFIGURED = "#236142"
MISSING = "#a12c32"
STRUCK_OUT = "#795119"
UNRESOLVED = "#596779"
DIFFERENCE = "#805312"

# Notice / banner surfaces.
WARNING_BG = "#fff5dc"
WARNING_BORDER = "#dac28b"
WARNING_TEXT = "#674912"
ERROR_BG = "#f8d7da"
ERROR_TEXT = "#842029"
INFO_BG = "#eaf0f8"
INFO_BORDER = "#c4d3e6"

# Evidence / diff accents (HTML fragments rendered inside QTextBrowser).
DIFF_DELETE = "#842029"
TABLE_CELL_TINT = "#eef4fb"

# --- spacing (prototype paddings/gaps, rounded to Qt-friendly values) -----

SPACING = 8
SPACING_TIGHT = 6
SPACING_CARD = 16
MARGIN_PAGE = 24
MARGIN_CARD = 12

#: Status label → badge color. Covers the three domain statuses plus the two
#: orthogonal UI hints (待人工核查 / 描述有差异); it adds no semantics.
STATUS_COLORS: dict[str, str] = {
    "已配置": CONFIGURED,
    "未配置": MISSING,
    "已划除": STRUCK_OUT,
    "待人工核查": UNRESOLVED,
    "描述有差异": DIFFERENCE,
}

_APP_STYLESHEET = f"""
QMainWindow, QDialog {{
    background: {BACKGROUND};
    color: {TEXT};
}}
QLabel {{ color: {TEXT}; }}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid #b9c4d1;
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: #c5ddfb;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {FOCUS_RING};
}}
QPushButton {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid #b9c4d1;
    border-radius: 4px;
    padding: 6px 12px;
}}
QPushButton:hover {{ background: #edf3fb; border-color: #7f9bbd; }}
QPushButton:disabled {{ color: {MUTED}; background: {CARD}; }}
QPushButton[primary="true"] {{
    background: {PRIMARY};
    color: {CARD};
    border: 1px solid {PRIMARY};
}}
QPushButton[primary="true"]:hover {{ background: {PRIMARY_DARK}; }}
QPushButton[primary="true"]:disabled {{
    color: #dbe4f0;
    background: #9db6d8;
    border-color: #9db6d8;
}}
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {CARD};
    text-align: center;
}}
QProgressBar::chunk {{ background: {PRIMARY}; }}
QSplitter::handle {{ background: {BORDER}; }}
QTableWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {PANEL_HEADING};
    color: {MUTED};
    border: 0;
    border-bottom: 1px solid {BORDER};
    padding: 6px 10px;
}}
QTabWidget::pane {{ border: 0; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent;
    border: 0;
    border-bottom: 3px solid transparent;
    padding: 12px 18px 9px 18px;
    color: {TEXT};
}}
QTabBar::tab:hover {{ color: {FOCUS_RING}; }}
QTabBar::tab:selected {{ color: {PRIMARY}; border-bottom: 3px solid {PRIMARY}; font-weight: 600; }}
QTabBar::tab:disabled {{ color: #9aa7b6; }}
"""


def apply_app_style(app: QApplication) -> None:
    """Apply the shared font, palette and stylesheet to the application.

    Called once at composition time (``__main__``) and from tests that build
    a standalone ``QApplication``. Safe to call multiple times.
    """
    font = QFont()
    font.setFamilies(list(FONT_FAMILIES))
    app.setFont(font)
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND))
    palette.setColor(QPalette.ColorRole.Base, QColor(CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(CARD))
    app.setPalette(palette)
    app.setStyleSheet(_APP_STYLESHEET)


def mark_primary(button: QPushButton) -> None:
    """Mark a button as the prototype's blue primary action (开始核查,
    保存检查项, …). Visual only — enabled/disabled logic stays with the
    owning widget."""
    button.setProperty("primary", True)


def status_badge_style(label_text: str) -> str:
    """Stylesheet for a status badge ``QLabel`` (result rows, detail header).

    Unknown statuses fall back to the muted color — unknown ≠ error.
    """
    color = STATUS_COLORS.get(label_text, MUTED)
    return f"color: {color}; font-weight: 600; background: transparent; padding: 1px 4px;"
