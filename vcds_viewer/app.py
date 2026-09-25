"""Punkt wejścia aplikacji VCDS LogScope."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .qt import QtCore, QtWidgets

from . import APP_NAME, __version__
from .mainwindow import MainWindow, app_icon
from .qt import exec_app


def _selftest(argv: list[str]) -> int:
    """Test dymny spakowanej aplikacji: ładuje log, buduje widoki, zapisuje zrzuty.

    Użycie: VCDS LogScope.exe --selftest [plik.csv] [katalog_wynikowy]
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    log_path = next((a for a in argv if a.lower().endswith((".csv", ".txt"))), None)
    if log_path is None:
        candidates = sorted(Path.cwd().glob("*.CSV")) + sorted(Path.cwd().glob("*.csv"))
        if not candidates:
            print("SELFTEST: brak pliku CSV do wczytania")
            return 2
        log_path = str(candidates[0])
    out_dir = Path(argv[-1]) if argv and not argv[-1].lower().endswith((".csv", ".txt")) else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QtWidgets.QApplication(sys.argv[:1])
    win = MainWindow()
    win.resize(1500, 900)
    win.ensurePolished()
    QtWidgets.QApplication.processEvents()

    win.open_path(log_path)
    QtWidgets.QApplication.processEvents()
    view = win.tabs.currentWidget()
    view.chart.set_cursor_x(20.4, emit=True)
    QtWidgets.QApplication.processEvents()

    # widok pasm: sprawdzamy, że pasy powstają i kursor je obsługuje
    view.cmb_view.setCurrentIndex(1)
    QtWidgets.QApplication.processEvents()
    win.grab()                      # wymusza przeliczenie układu pasm
    view.bands.set_cursor_x(20.4, emit=True)
    QtWidgets.QApplication.processEvents()
    bands = len(view.bands.visible_lanes())

    from .compare import CompareView
    from .parser import parse_log

    log = parse_log(log_path)
    cmp_view = CompareView([log, log], win.theme, win)
    cmp_view.resize(1400, 800)
    cmp_view.ensurePolished()
    cmp_view.chart.set_cursor_x(20.4, emit=True)
    cmp_view.tabs.setCurrentIndex(1)
    QtWidgets.QApplication.processEvents()

    ok = True
    lines: list[str] = []
    for widget, name in ((win, "selftest_log"), (cmp_view, "selftest_porownanie")):
        path = out_dir / f"{name}.png"
        ok = widget.grab().save(str(path)) and ok
        lines.append(f"SELFTEST: zapisano {path}")

    # --- kursor przy OBU osiach: pasek statusu musi dostać prawdziwy czas i obroty.
    # Regresja z 1.0.6: okno porównania przy osi obrotów wysyłało obroty jako czas
    # („kursor: 4640,00 s” zamiast np. „55,48 s”), a „obroty:” zostawało puste.
    import numpy as np                     # lokalnie: start programu go nie potrzebuje

    series = log.rpm_series()
    rpms = np.asarray(series[0], dtype=float) if series else np.array([])
    rpms = rpms[np.isfinite(rpms)]
    probe_rpm = float(np.median(rpms)) if len(rpms) else 3000.0

    cursor_ok = True
    seen: list[tuple[float, float]] = []
    for w in (view, cmp_view):
        w.cursorMoved.connect(lambda t, rpm, _src: seen.append((t, rpm)))
    cmp_view.cursorMoved.connect(win._on_cursor)          # tak jak w programie

    for w, name in ((view, "pojedynczy log"), (cmp_view, "porównanie")):
        for idx, axis, x in ((0, "czas", 20.4), (1, "obroty", probe_rpm)):
            w.cmb_x.setCurrentIndex(idx)
            QtWidgets.QApplication.processEvents()
            seen.clear()
            w.chart.set_cursor_x(x, emit=True)
            QtWidgets.QApplication.processEvents()
            t_val, rpm_val = seen[-1] if seen else (float("nan"), float("nan"))
            lines.append(f"SELFTEST: kursor {name} / oś {axis}: "
                         f"{win.lbl_cursor.text()}, obroty: {win.lbl_rpm.text()}")
            if idx == 1 and not (t_val == t_val and 0.0 <= t_val < 600.0):
                cursor_ok = False       # czas nie może być wartością obrotów
            if not (rpm_val == rpm_val and rpm_val > 0):
                cursor_ok = False       # obroty nie mogą zostać puste

    params = len(cmp_view.params)
    rows = len(cmp_view.grid)
    channels = len(view.log.numeric_channels)
    lines.append(f"SELFTEST: wersja {__version__}")
    lines.append(f"SELFTEST: log={Path(log_path).name} kanaly={channels} wiersze={view.log.n_rows} "
                 f"parametry_wspolne={params} siatka={rows} pasma={bands}")
    good = ok and channels and params and bands and cursor_ok
    lines.append("SELFTEST: OK" if good else "SELFTEST: BLAD")

    report = out_dir / "selftest_report.txt"
    report.write_text("\n".join(lines), encoding="utf-8")
    if sys.stdout is not None:      # w wersji .exe (--windowed) brak konsoli
        print("\n".join(lines))
    return 0 if good else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest(sys.argv)
    if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("VCDS-LogScope")
    app.setWindowIcon(app_icon())
    win = MainWindow()
    win.show()
    if "--selftest-gui" in sys.argv:
        # test dymny: pełny start GUI (z pętlą zdarzeń), zamyka się sam po 4 sekundach
        log_path = next((a for a in sys.argv[1:] if a.lower().endswith((".csv", ".txt"))), None)
        if log_path:
            win.open_path(log_path)
        QtCore.QTimer.singleShot(4000, app.quit)
    return exec_app(app)


if __name__ == "__main__":
    sys.exit(main())
