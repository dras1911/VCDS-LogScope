"""Motywy (ciemny/jasny) i arkusz stylów Qt."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    window: str
    panel: str
    panel_alt: str
    plot_bg: str
    grid: str
    text: str
    text_dim: str
    accent: str
    accent_text: str
    border: str
    row_alt: str
    cursor: str
    selection: str
    tooltip_bg: str
    tooltip_border: str

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


DARK = Theme(
    name="dark",
    window="#14161a",
    panel="#1b1e24",
    panel_alt="#22262e",
    plot_bg="#171a1f",
    grid="#2c313a",
    text="#e8eaed",
    text_dim="#9aa0a6",
    accent="#4c8df6",
    accent_text="#ffffff",
    border="#2e333c",
    row_alt="#1f2329",
    cursor="#d8dce2",
    selection="#2b3a55",
    tooltip_bg="#1f2329",
    tooltip_border="#3a4049",
)

LIGHT = Theme(
    name="light",
    window="#f2f3f5",
    panel="#ffffff",
    panel_alt="#f7f8fa",
    plot_bg="#ffffff",
    grid="#dcdfe4",
    text="#1f2328",
    text_dim="#6b7280",
    accent="#2563eb",
    accent_text="#ffffff",
    border="#d5d8dd",
    row_alt="#f5f6f8",
    cursor="#3b4149",
    selection="#d8e4fb",
    tooltip_bg="#1f2329",
    tooltip_border="#3a4049",
)

THEMES = {"dark": DARK, "light": LIGHT}


def stylesheet(t: Theme) -> str:
    """Arkusz stylów aplikacji dla wybranego motywu."""
    return f"""
    QWidget {{
        background: {t.window};
        color: {t.text};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 9.5pt;
    }}
    QMainWindow, QDialog {{ background: {t.window}; }}

    QMenuBar {{ background: {t.panel}; border-bottom: 1px solid {t.border}; }}
    QMenuBar::item {{ padding: 5px 10px; background: transparent; }}
    QMenuBar::item:selected {{ background: {t.accent}; color: {t.accent_text}; border-radius: 4px; }}
    QMenu {{ background: {t.panel}; border: 1px solid {t.border}; padding: 4px; }}
    QMenu::item {{ padding: 5px 22px 5px 12px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {t.accent}; color: {t.accent_text}; }}
    QMenu::separator {{ height: 1px; background: {t.border}; margin: 4px 6px; }}

    QToolBar {{
        background: {t.panel}; border: none; border-bottom: 1px solid {t.border};
        padding: 5px 6px; spacing: 6px;
    }}
    QToolBar QToolButton {{
        background: {t.panel_alt}; border: 1px solid {t.border}; border-radius: 6px;
        padding: 5px 10px; color: {t.text};
    }}
    QToolBar QToolButton:hover {{ background: {t.accent}; color: {t.accent_text}; border-color: {t.accent}; }}
    QToolBar QToolButton:checked {{ background: {t.accent}; color: {t.accent_text}; border-color: {t.accent}; }}
    QToolBar QToolButton:disabled {{ color: {t.text_dim}; background: {t.panel}; }}

    QPushButton {{
        background: {t.panel_alt}; border: 1px solid {t.border}; border-radius: 6px;
        padding: 5px 12px; color: {t.text};
    }}
    QPushButton:hover {{ border-color: {t.accent}; }}
    QPushButton:pressed {{ background: {t.accent}; color: {t.accent_text}; }}
    QPushButton:checked {{ background: {t.accent}; color: {t.accent_text}; border-color: {t.accent}; }}
    QPushButton:disabled {{ color: {t.text_dim}; }}
    QPushButton#primary {{ background: {t.accent}; color: {t.accent_text}; border: none; font-weight: 600; }}

    QTabWidget::pane {{ border: 1px solid {t.border}; border-radius: 6px; background: {t.panel}; top: -1px; }}
    QTabBar::tab {{
        background: {t.panel_alt}; color: {t.text_dim}; padding: 6px 16px;
        border: 1px solid {t.border}; border-bottom: none;
        border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 3px;
    }}
    QTabBar::tab:selected {{ background: {t.panel}; color: {t.text}; font-weight: 600; }}
    QTabBar::tab:hover {{ color: {t.text}; }}

    QSplitter::handle {{ background: {t.border}; }}
    QSplitter::handle:horizontal {{ width: 2px; }}
    QSplitter::handle:vertical {{ height: 2px; }}

    QListWidget, QTreeWidget, QTableWidget, QTableView {{
        background: {t.panel}; alternate-background-color: {t.row_alt};
        border: 1px solid {t.border}; border-radius: 6px;
        selection-background-color: {t.selection}; selection-color: {t.text};
        gridline-color: {t.border};
    }}
    QListWidget::item {{ padding: 4px 6px; border-radius: 4px; }}
    QListWidget::item:selected {{ background: {t.selection}; }}
    QHeaderView::section {{
        background: {t.panel_alt}; color: {t.text_dim}; padding: 5px 6px;
        border: none; border-right: 1px solid {t.border}; border-bottom: 1px solid {t.border};
        font-weight: 600;
    }}
    QHeaderView::section:hover {{ color: {t.text}; }}
    QTableView QTableCornerButton::section {{ background: {t.panel_alt}; border: none; }}

    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {t.panel_alt}; border: 1px solid {t.border}; border-radius: 6px;
        padding: 4px 8px; color: {t.text}; selection-background-color: {t.accent};
    }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{ background: {t.panel}; border: 1px solid {t.border}; }}
    /* nieaktywne pola (np. „Przesunięcie” przy osi obrotów) — wyraźnie wyszarzone */
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        color: {t.text_dim}; background: {t.panel}; border: 1px solid {t.border};
    }}
    QSpinBox:disabled QLineEdit, QDoubleSpinBox:disabled QLineEdit {{
        color: {t.text_dim}; background: {t.panel};
    }}
    QDoubleSpinBox:disabled::up-button, QDoubleSpinBox:disabled::down-button,
    QSpinBox:disabled::up-button, QSpinBox:disabled::down-button {{ background: {t.panel}; }}
    QLabel:disabled {{ color: {t.text_dim}; }}

    QCheckBox {{ spacing: 6px; }}
    QCheckBox::indicator {{
        width: 14px; height: 14px; border: 1px solid {t.border};
        border-radius: 3px; background: {t.panel_alt};
    }}
    QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.accent}; }}

    QStatusBar {{ background: {t.panel}; border-top: 1px solid {t.border}; color: {t.text_dim}; }}
    QStatusBar QLabel {{ color: {t.text_dim}; padding: 0 6px; }}

    QScrollBar:vertical {{ background: {t.panel}; width: 11px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 5px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {t.accent}; }}
    QScrollBar:horizontal {{ background: {t.panel}; height: 11px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 5px; min-width: 24px; }}
    QScrollBar::handle:horizontal:hover {{ background: {t.accent}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QGroupBox {{
        border: 1px solid {t.border}; border-radius: 6px; margin-top: 10px; padding-top: 8px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {t.text_dim}; }}

    QLabel#hint {{ color: {t.text_dim}; }}
    QLabel#dropzone {{
        color: {t.text_dim}; border: 2px dashed {t.border}; border-radius: 10px;
        padding: 40px; font-size: 12pt;
    }}
    QToolTip {{
        background: {t.tooltip_bg}; color: #e8eaed; border: 1px solid {t.tooltip_border};
        padding: 4px 6px; border-radius: 4px;
    }}
    """
