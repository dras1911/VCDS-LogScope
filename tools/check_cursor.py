"""Co dokładnie leci do paska statusu z okna porównania (diagnostyka zgłoszeń).

Przy osi obrotów pasek statusu musi dostać CZAS zdarzenia i OBROTY — nie pozycję osi
(regresja z 1.0.5: pokazywał „kursor: 4640,00 s”).

Użycie:
    .venv/Scripts/python.exe tools/check_cursor.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("VCDS_LOGSCOPE_SETTINGS", "VCDS-LogScope-test")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.compare import CompareView  # noqa: E402
from vcds_viewer.formatting import fmt_num, fmt_time  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.qt import QtWidgets  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402

SHOTS = ROOT / "build" / "shots"


def main() -> int:
    app = QtWidgets.QApplication(sys.argv[:1])
    logs = [parse_log(ROOT / "LOG-01-031-002-011-V10.CSV"),
            parse_log(ROOT / "LOG-01-020-115-118-V10.CSV")]
    view = CompareView(logs, DARK)
    view.resize(1560, 940)
    view.ensurePolished()
    got: list[tuple] = []
    view.cursorMoved.connect(lambda t, rpm, _v: got.append((t, rpm)))

    print("--- oś czasu ---")
    view.chart.set_cursor_x(30.0, emit=True)
    t, rpm = got[-1]
    print(f"  kursor na 30,0 s   -> pasek statusu: {fmt_time(t)} s  |  {fmt_num(rpm)} obr/min")

    print("--- oś obrotów ---")
    view.cmb_x.setCurrentIndex(1)
    view.chart.set_cursor_x(3200.0, emit=True)
    t, rpm = got[-1]
    print(f"  kursor na 3200 obr -> pasek statusu: {fmt_time(t)} s  |  {fmt_num(rpm)} obr/min")
    print(f"  (oczekiwany czas: próbka o 3200 obr/min, nie 3200 sekund)")

    # nagłówki tabeli przy wąskiej kolumnie
    view.tabs.setCurrentIndex(0)
    view.resize(900, 700)
    QtWidgets.QApplication.processEvents()
    view.grab()
    SHOTS.mkdir(parents=True, exist_ok=True)
    shot = SHOTS / "50_tabela_waska_kolumna.png"
    view.grab().save(str(shot))
    print("zapisano:", shot)
    titles = [g.title for g in logs[0].groups] if logs[0].groups else []
    print("pełne tytuły grup:", titles)
    view.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
