"""Zrzut ekranu dla wskazanego logu (weryfikacja na prawdziwych danych).

Użycie: QT_QPA_PLATFORM= .venv/Scripts/python.exe tools/shot_log.py LOG-....CSV [nazwa]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("VCDS_LOGSCOPE_SETTINGS", "VCDS-LogScope-test")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.qt import QtWidgets  # noqa: E402

from vcds_viewer.logview import LogView  # noqa: E402
from vcds_viewer.mainwindow import MainWindow  # noqa: E402

OUT = ROOT / "build" / "shots"


def main() -> int:
    log_path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "LOG-01-031-002-011-V10.CSV")
    name = sys.argv[2] if len(sys.argv) > 2 else "realny"
    app = QtWidgets.QApplication(sys.argv[:1])
    win = MainWindow()
    win.resize(1660, 1000)
    win.ensurePolished()
    QtWidgets.QApplication.processEvents()
    win.open_path(log_path)
    QtWidgets.QApplication.processEvents()
    view: LogView = win.tabs.currentWidget()
    view.chart.set_cursor_x(view.log.t_start + view.log.duration * 0.45, emit=True)
    QtWidgets.QApplication.processEvents()
    OUT.mkdir(parents=True, exist_ok=True)
    p1 = OUT / f"09_{name}_wykres.png"
    win.grab().save(str(p1))
    print(f"zapisano: {p1}")

    win.set_view_mode("table")
    QtWidgets.QApplication.processEvents()
    p2 = OUT / f"10_{name}_tabela.png"
    win.grab().save(str(p2))
    print(f"zapisano: {p2}")

    view.cmb_x.setCurrentIndex(1)
    win.set_view_mode("both")
    QtWidgets.QApplication.processEvents()
    view.chart.set_cursor_x(3000.0, emit=True)
    QtWidgets.QApplication.processEvents()
    p3 = OUT / f"11_{name}_rpm.png"
    win.grab().save(str(p3))
    print(f"zapisano: {p3}")

    # sprawdzenie unikalności kolorów na prawdziwym logu
    colors = list(view.colors.values())
    print(f"kanaly={len(colors)} unikalne_kolory={len(set(colors))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
