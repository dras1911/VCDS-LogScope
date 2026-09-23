"""Zrzut widoku pasm — narzędzie pomocnicze do oceny wyglądu.

Użycie: QT_QPA_PLATFORM= .venv/Scripts/python.exe tools/shot_bands.py [log.csv]
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
    rpm_axis = "--rpm" in sys.argv
    app = QtWidgets.QApplication(sys.argv[:1])
    win = MainWindow()
    win.resize(1660, 1040)
    win.open_path(log)
    view = win.tabs.currentWidget()
    win.set_view_mode("chart")
    QtWidgets.QApplication.processEvents()
    if rpm_axis:
        view.cmb_x.setCurrentIndex(1)
        QtWidgets.QApplication.processEvents()
    view.cmb_view.setCurrentIndex(1)          # Widok: Pasma
    QtWidgets.QApplication.processEvents()
    win.grab()                                # wymusza przeliczenie układu pasm
    QtWidgets.QApplication.processEvents()
    view.bands.set_cursor_x(3.6 if not rpm_axis else 3000.0, emit=True)
    QtWidgets.QApplication.processEvents()
    out = ROOT / "build" / "shots" / ("21_pasma_rpm.png" if rpm_axis else "20_pasma.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    win.grab().save(str(out))
    print(f"zapisano: {out}")
    print(f"pasow: {len(view.bands._lanes)}  widocznych: {len(view.bands.visible_lanes())}")
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
