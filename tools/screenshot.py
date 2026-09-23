"""Zrzuty ekranu aplikacji do weryfikacji wizualnej (tryb offscreen).

Użycie:  .venv/Scripts/python.exe tools/screenshot.py [katalog_wynikowy]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("VCDS_LOGSCOPE_SETTINGS", "VCDS-LogScope-test")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.qt import QtCore, QtWidgets  # noqa: E402

from vcds_viewer.compare import CompareView  # noqa: E402
from vcds_viewer.logview import LogView  # noqa: E402
from vcds_viewer.mainwindow import MainWindow  # noqa: E402
from vcds_viewer.parser import parse_log, read_text  # noqa: E402

SAMPLE = ROOT / "tests" / "data" / "przyklad.csv"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "shots"


def make_variant(path: Path, out: Path) -> Path:
    """Tworzy zmodyfikowany log (symulacja „przed/po” regulacji)."""
    lines = read_text(path).split("\n")
    out_lines = []
    for i, line in enumerate(lines):
        if i < 7 or not line.strip():
            out_lines.append(line)
            continue
        fields = line.split(",")
        try:
            fields[8] = f"{float(fields[8]) * 0.93:.1f}"      # obciążenie -7%
            fields[10] = f"{float(fields[10]) * 1.08:.2f}"    # przepływ +8%
            fields[7] = f"{int(int(fields[7]) * 1.02)}"       # obroty +2%
        except (ValueError, IndexError):
            pass
        out_lines.append(",".join(fields))
    out.write_text("\n".join(out_lines), encoding="cp1250")
    return out


def shot(widget: QtWidgets.QWidget, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    widget.ensurePolished()
    QtWidgets.QApplication.processEvents()
    pix = widget.grab()
    path = OUT / f"{name}.png"
    pix.save(str(path))
    print(f"zapisano: {path}  ({pix.width()}x{pix.height()})")


def main() -> int:
    app = QtWidgets.QApplication(sys.argv[:1])
    win = MainWindow()
    win.resize(1660, 1000)
    if os.environ.get("SHOW_WINDOWS") == "1":
        win.show()
    win.ensurePolished()
    QtWidgets.QApplication.processEvents()

    win.open_path(str(SAMPLE))
    QtWidgets.QApplication.processEvents()
    view: LogView = win.tabs.currentWidget()
    view.chart.resize(1200, 620)
    QtWidgets.QApplication.processEvents()
    view.chart.set_cursor_x(20.4, emit=True)
    QtWidgets.QApplication.processEvents()
    shot(win, "01_wykres")

    # tabela
    win.set_view_mode("table")
    QtWidgets.QApplication.processEvents()
    view.table.highlight_time(20.4, follow=True)
    QtWidgets.QApplication.processEvents()
    shot(win, "02_tabela")
    win.set_view_mode("both")

    # wykres w trybie RPM
    view.cmb_x.setCurrentIndex(1)
    QtWidgets.QApplication.processEvents()
    view.chart.set_cursor_x(3600.0, emit=True)
    QtWidgets.QApplication.processEvents()
    shot(win, "03_wykres_rpm")
    view.cmb_x.setCurrentIndex(0)

    # porównanie
    variant = make_variant(SAMPLE, OUT / "LOG-01-031-002-011-V10_B.CSV")
    log_a = parse_log(SAMPLE)
    log_b = parse_log(variant)
    cmp_view = CompareView([log_a, log_b], win.theme, None)
    cmp_view.resize(1600, 950)
    if os.environ.get("SHOW_WINDOWS") == "1":
        cmp_view.show()
    cmp_view.ensurePolished()
    QtWidgets.QApplication.processEvents()
    cmp_view.chart.set_cursor_x(20.4, emit=True)
    QtWidgets.QApplication.processEvents()
    shot(cmp_view, "04_porownanie_wykres")
    cmp_view.tabs.setCurrentIndex(1)
    QtWidgets.QApplication.processEvents()
    shot(cmp_view, "05_porownanie_tabela")
    cmp_view.tabs.setCurrentIndex(2)
    QtWidgets.QApplication.processEvents()
    shot(cmp_view, "06_porownanie_statystyki")

    # motyw jasny
    win.apply_theme(__import__("vcds_viewer.theme", fromlist=["LIGHT"]).LIGHT)
    win.set_view_mode("both")
    QtWidgets.QApplication.processEvents()
    view.chart.set_cursor_x(20.4, emit=True)
    QtWidgets.QApplication.processEvents()
    shot(win, "07_jasny_motyw")

    # stan pusty
    win2 = MainWindow()
    win2.resize(1200, 700)
    if os.environ.get("SHOW_WINDOWS") == "1":
        win2.show()
    win2.ensurePolished()
    QtWidgets.QApplication.processEvents()
    shot(win2, "08_stan_pusty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
