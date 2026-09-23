"""Zrzut wykresu przy osi obrotów w trybie linii (diagnostyka pętli).

Użycie: QT_QPA_PLATFORM= .venv/Scripts/python.exe tools/shot_rpm_lines.py [log.csv]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("VCDS_LOGSCOPE_SETTINGS", "VCDS-LogScope-test")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.mainwindow import MainWindow  # noqa: E402
from vcds_viewer.qt import QtWidgets  # noqa: E402


def main() -> int:
    log = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "LOG-01-031-002-011-V10.CSV")
    app = QtWidgets.QApplication(sys.argv[:1])
    win = MainWindow()
    win.resize(1660, 1040)
    win.open_path(log)
    view = win.tabs.currentWidget()
    win.set_view_mode("chart")
    QtWidgets.QApplication.processEvents()
    view.cmb_x.setCurrentIndex(1)                 # oś obrotów
    QtWidgets.QApplication.processEvents()
    view.cmb_draw.setCurrentIndex(0)              # Linia (jak na zrzucie użytkownika)
    QtWidgets.QApplication.processEvents()
    # zostawiamy tylko obciążenie i przepływ — dwa parametry, łatwiej ocenić pętle
    keep = ("obciążenie", "przepływu")
    for i in range(view.panel.list.count()):
        item = view.panel.list.item(i)
        sid = str(item.data(0x0100))          # Qt.UserRole
        checked = any(k in sid.lower() for k in keep)
        from vcds_viewer.qt import Qt
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
    QtWidgets.QApplication.processEvents()
    view.chart.fit()
    view.chart.set_cursor_x(3900, emit=True)
    win.grab()
    QtWidgets.QApplication.processEvents()

    out = ROOT / "build" / "shots" / "50_obroty_linia.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    win.grab().save(str(out))
    print(f"zapisano: {out}")
    print("serie na wykresie:", [s.spec.short for s in view.chart.visible_series()])
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
