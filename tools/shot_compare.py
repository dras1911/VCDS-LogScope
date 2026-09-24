"""Zrzuty okna porównania: dopasowanie w czasie, log bazowy, oś obrotów.

Użycie: .venv/Scripts/python.exe tools/shot_compare.py [logA.csv] [logB.csv]
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

SHOTS = ROOT / "build" / "shots"


def save(view: CompareView, name: str):
    QtWidgets.QApplication.processEvents()
    view.grab()
    QtWidgets.QApplication.processEvents()
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = SHOTS / name
    view.grab().save(str(out))
    print("zapisano:", out)


def main() -> int:
    args = [a for a in sys.argv[1:] if a.lower().endswith((".csv", ".txt"))]
    paths = args or [str(ROOT / "LOG-01-031-002-011-V10.CSV"),
                     str(ROOT / "LOG-01-020-115-118-V10.CSV")]
    app = QtWidgets.QApplication(sys.argv[:1])
    logs = [parse_log(p) for p in paths]
    view = CompareView(logs, DARK)
    view.resize(1560, 940)
    view.ensurePolished()
    view.chart.set_cursor_x(30.0, emit=True)

    print(f"log bazowy: {view.tags[view.base]}   przesuniecie: {view.offset_b:+.2f} s")
    print("podpowiedz:", view.lbl_hint.text())
    save(view, "40_porownanie_parametry.png")

    # tabela różnic po zmianie logu bazowego
    view._on_base(1)
    view.tabs.setCurrentIndex(1)
    print(f"po zmianie bazy: {view.tags[view.base]}   przesuniecie: {view.offset_b:+.2f} s")
    print("naglowki tabeli:", [view.model.headerText(c) for c in range(view.model.columnCount())][:6])
    save(view, "41_porownanie_baza_B.png")

    # oś obrotów
    view.tabs.setCurrentIndex(0)
    view.cmb_x.setCurrentIndex(1)
    print("os X:", view.x_mode, " rysowanie:", view.cmb_draw.currentData(),
          " dopasowanie aktywne:", view.btn_align.isEnabled())
    view.chart.set_cursor_x(3000.0, emit=True)
    save(view, "42_porownanie_obroty.png")

    wspolne = sum(1 for p in view.params if p.common)
    print(f"parametrow w panelu: {len(view.params)}  (wspolnych: {wspolne}, "
          f"tylko w jednym logu: {len(view.params) - wspolne})")
    view.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
