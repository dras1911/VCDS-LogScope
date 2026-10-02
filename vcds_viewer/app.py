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

    # ślad postępu: przy zawieszeniu na maszynie bez użytkownika widać, na którym
    # kroku stanął autotest (build_exe pokazuje ten plik przy niepowodzeniu)
    trace = out_dir / "selftest_trace.txt"

    def _note(step: str) -> None:
        try:
            with trace.open("a", encoding="utf-8") as fh:
                fh.write(step + "\n")
                fh.flush()
        except OSError:
            pass

    import threading

    # awaryjne wyjście: gdyby zamknięcie blokowało się bez końca (np. niewidoczny
    # komunikat modalny na maszynie bez użytkownika), smoke dostanie kod 9
    # zamiast wisieć godzinami
    _failsafe = threading.Timer(240.0, os._exit, args=(9,))
    _failsafe.daemon = True
    _failsafe.start()
    _note("start")

    app = QtWidgets.QApplication(sys.argv[:1])
    _note("qapp")
    win = MainWindow()
    _note("okno")
    win.resize(1500, 900)
    win.ensurePolished()
    QtWidgets.QApplication.processEvents()

    win.open_path(log_path)
    QtWidgets.QApplication.processEvents()
    _note("log")
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
    _note("pasma")

    from .compare import CompareView
    from .parser import parse_log

    log = parse_log(log_path)
    # parent=None: gdyby okno porównania było dzieckiem okna głównego, jego zawartość
    # nakładałaby się na zrzut `win.grab()` (stary artefakt selftestu)
    cmp_view = CompareView([log, log], win.theme, None)
    cmp_view.resize(1400, 800)
    cmp_view.ensurePolished()
    cmp_view.chart.set_cursor_x(20.4, emit=True)
    cmp_view.tabs.setCurrentIndex(1)
    QtWidgets.QApplication.processEvents()
    _note("porownanie")

    ok = True
    lines: list[str] = []
    for widget, name in ((win, "selftest_log"), (cmp_view, "selftest_porownanie")):
        path = out_dir / f"{name}.png"
        ok = widget.grab().save(str(path)) and ok
        lines.append(f"SELFTEST: zapisano {path}")
    _note("zrzuty")

    # --- kursor przy OBU osiach: pasek statusu musi dostać prawdziwy czas i obroty.
    # Regresja z 1.0.6: okno porównania przy osi obrotów wysyłało obroty jako czas
    # („kursor: 4640,00 s” zamiast np. „55,48 s”), a „obroty:” zostawało puste.
    import numpy as np                     # lokalnie: start programu go nie potrzebuje
    from .model import X_RPM, X_TIME

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

    # --- zaznaczony fragment: statystyki liczą się wyłącznie z zaznaczonych próbek
    sel_ok = False
    try:
        ch0 = view.log.numeric_channels[0]
        dur = view.log.duration
        view.cmb_x.setCurrentIndex(0)                 # oś czasu
        QtWidgets.QApplication.processEvents()
        view.chk_select.setChecked(True)
        view.chart.set_selection(dur * 0.2, dur * 0.5)
        QtWidgets.QApplication.processEvents()
        cards = [view.sel_stats.cards_layout.itemAt(i).widget()
                 for i in range(view.sel_stats.cards_layout.count())]
        cards = [c for c in cards if c is not None]
        n_time, _lo, _hi, _mean = view.log.stats_in_range(ch0, X_TIME, dur * 0.2, dur * 0.5)
        # to samo przy osi obrotów — zakres znaczy wtedy „obroty od–do”
        view.cmb_x.setCurrentIndex(1)
        QtWidgets.QApplication.processEvents()
        view.chart.set_selection(2000.0, 3000.0)
        QtWidgets.QApplication.processEvents()
        n_rpm, _lo2, _hi2, _mean2 = view.log.stats_in_range(ch0, X_RPM, 2000.0, 3000.0)
        sel_ok = bool(cards) and not view.sel_stats.isHidden() and n_time > 0 and n_rpm > 0
        lines.append(f"SELFTEST: zaznaczony fragment: {len(cards)} parametrów, "
                     f"próbek={n_time} (czas) / {n_rpm} (obroty) "
                     f"({cards[0].text() if cards else '—'})")
    except Exception as exc:                 # raport zamiast wyjątku znikąd
        lines.append(f"SELFTEST: zaznaczony fragment: BŁĄD {exc}")
    view.chk_select.setChecked(False)
    view.cmb_x.setCurrentIndex(0)
    QtWidgets.QApplication.processEvents()
    _note("zaznaczenie")

    # --- suwaki pod wykresem: przesuwanie i powiększanie muszą działać w obu oknach
    nav_ok = False
    try:
        view.cmb_view.setCurrentIndex(0)          # na wierzch wykres nakładany
        QtWidgets.QApplication.processEvents()
        parts: list[str] = []
        checks: list[bool] = []
        for w, name in ((view, "pojedynczy log"), (cmp_view, "porównanie")):
            chart = w.chart
            nav = chart.nav
            r0a, r0b = chart.vb.viewRange()[0]
            span0 = r0b - r0a
            nav.zoom.setValue(nav.ZOOM_STEPS // 2)     # pół suwaka powiększenia
            QtWidgets.QApplication.processEvents()
            z0, z1 = chart.vb.viewRange()[0]
            zoomed = (z1 - z0) < span0 - 1e-9
            nav.scroll.setValue(nav.scroll.maximum())  # suwak widoku na koniec logu
            QtWidgets.QApplication.processEvents()
            a0, a1 = chart.vb.viewRange()[0]
            moved = a0 > z0 + 1e-9                     # ruszył się WZGLĘDEM przybliżenia
            parts.append(f"{name}: powiększenie={'OK' if zoomed else 'BŁĄD'}, "
                         f"przesunięcie={'OK' if moved else 'BŁĄD'}")
            checks += [zoomed, moved]
            chart.fit()                            # przywróć widok dla dalszych kroków
            QtWidgets.QApplication.processEvents()
        nav_ok = len(checks) == 4 and all(checks)
        lines.append("SELFTEST: suwaki: " + "; ".join(parts))
    except Exception as exc:             # raport zamiast wyjątku znikąd
        lines.append(f"SELFTEST: suwaki: BŁĄD {exc}")
    _note("suwaki")

    # zrzut z przybliżeniem zrobionym suwakiem (dowód dla przeglądu wydania)
    try:
        view.chart.nav.zoom.setValue(400)
        QtWidgets.QApplication.processEvents()
        ok = win.grab().save(str(out_dir / "selftest_suwaki.png")) and ok
        lines.append(f"SELFTEST: zapisano {out_dir / 'selftest_suwaki.png'}")
    except Exception as exc:
        lines.append(f"SELFTEST: zrzut suwaków: BŁĄD {exc}")

    _note("raport")
    lines.append(f"SELFTEST: wersja {__version__}")
    lines.append(f"SELFTEST: log={Path(log_path).name} kanaly={channels} wiersze={view.log.n_rows} "
                 f"parametry_wspolne={params} siatka={rows} pasma={bands}")
    good = ok and channels and params and bands and cursor_ok and sel_ok and nav_ok
    lines.append(f"SELFTEST: kontrole: obrazy={ok} kanaly={bool(channels)} parametry={bool(params)} "
                 f"pasma={bool(bands)} kursor={cursor_ok} zaznaczenie={sel_ok} suwaki={nav_ok}")
    lines.append("SELFTEST: OK" if good else "SELFTEST: BLAD")

    report = out_dir / "selftest_report.txt"
    report.write_text("\n".join(lines), encoding="utf-8")
    if sys.stdout is not None:      # w wersji .exe (--windowed) brak konsoli
        print("\n".join(lines))
    # Tryb testowy kończymy twardo: w spakowanej aplikacji na maszynach CI zamknięcie
    # interpretera potrafi zawisnąć po wykonanej pracy (objaw: raport gotowy, proces
    # żyje do limitu smoke), a os._exit gwarantuje deterministyczne zakończenie.
    try:
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(0 if good else 1)


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
    marker: Path | None = None
    if "--selftest-gui" in sys.argv:
        # test dymny: pełny start GUI (z pętlą zdarzeń), sam się zamyka po 4 sekundach
        import threading
        log_path = next((a for a in sys.argv[1:] if a.lower().endswith((".csv", ".txt"))), None)
        if log_path:
            win.open_path(log_path)
        marker = Path.cwd() / "selftest_gui.marker"

        def _mark(text: str) -> None:
            try:
                marker.write_text(text, encoding="utf-8")
            except OSError:
                pass

        def _quit() -> None:
            _mark("timer")
            app.quit()

        _mark("petla")
        QtCore.QTimer.singleShot(4000, _quit)
        # awaryjne wyjście: gdyby quit() nie zakończył pętli (np. modalny komunikat
        # schowany na maszynie bez użytkownika), smoke dostanie kod 9 zamiast wisieć
        _failsafe_gui = threading.Timer(30.0, os._exit, args=(9,))
        _failsafe_gui.daemon = True
        _failsafe_gui.start()
    rc = exec_app(app)
    # tryb testowy kończymy twardo (deterministycznie) — w spakowanej aplikacji na CI
    # samo zamknięcie potrafi zawisnąć po zakończeniu pętli zdarzeń
    if marker is not None:
        try:
            marker.write_text(f"koniec rc={rc}", encoding="utf-8")
        except OSError:
            pass
        try:
            sys.stdout.flush()
        except Exception:
            pass
        os._exit(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
