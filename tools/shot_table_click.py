"""Zrzut: klik w wiersz tabeli przy osi obrotów (kursor ma być widoczny i na właściwym wierszu).

Użycie: QT_QPA_PLATFORM= .venv/Scripts/python.exe tools/shot_table_click.py [log.csv]
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
    view.cmb_x.setCurrentIndex(1)             # oś obrotów
    QtWidgets.QApplication.processEvents()
    win.grab()
    QtWidgets.QApplication.processEvents()

    group = view.log.groups[1]
    row = len(group.t) - 6                    # wiersz blisko końca logu (wysokie obroty)
    t = float(group.t[row])
    view.set_cursor_time(t)                   # to samo, co klik w wiersz tabeli
    view.table.highlight_time(t, follow=False)
    QtWidgets.QApplication.processEvents()

    out = ROOT / "build" / "shots" / "30_klik_w_tabeli.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    win.grab().save(str(out))
    lo, hi = view.chart.plot.vb.viewRange()[0]
    print(f"zapisano: {out}")
    print(f"klikniety wiersz: {row}  czas: {t:.2f} s  kursor_x: {view.chart.cursor_x():.0f}")
    print(f"zakres osi X: {lo:.0f} .. {hi:.0f}  (kursor w zakresie: {lo <= view.chart.cursor_x() <= hi})")
    print(f"podswietlony wiersz w tabeli: {view.table.model.hover_rows.get(group.letter)}")
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
