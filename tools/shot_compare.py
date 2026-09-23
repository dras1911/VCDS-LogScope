"""Zrzut okna porównania dwóch logów (do oceny wyglądu i weryfikacji listy parametrów).

Użycie: QT_QPA_PLATFORM= .venv/Scripts/python.exe tools/shot_compare.py [logA.csv] [logB.csv]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("VCDS_LOGSCOPE_SETTINGS", "VCDS-LogScope-test")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.compare import CompareView  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.qt import QtWidgets  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:] if a.lower().endswith((".csv", ".txt"))]
    paths = args or [str(ROOT / "LOG-01-031-002-011-V10.CSV"),
                     str(ROOT / "LOG-01-020-115-118-V10.CSV")]
    app = QtWidgets.QApplication(sys.argv[:1])
    logs = [parse_log(p) for p in paths]
    view = CompareView(logs, DARK)
    view.resize(1560, 940)
    view.ensurePolished()
    QtWidgets.QApplication.processEvents()
    view.chart.set_cursor_x(30.0, emit=True)
    view.grab()                       # wymusza przeliczenie układu
    QtWidgets.QApplication.processEvents()

    out = ROOT / "build" / "shots" / "40_porownanie_parametry.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    view.grab().save(str(out))
    wspolne = sum(1 for p in view.params if p.common)
    print(f"zapisano: {out}")
    print(f"parametrow w panelu: {len(view.params)}  (wspolnych: {wspolne}, "
          f"tylko w jednym logu: {len(view.params) - wspolne})")
    view.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
