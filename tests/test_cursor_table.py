"""Testy powiązania tabeli z kursorem wykresu (w obu trybach osi X).

Pilnują, żeby kliknięcie wiersza tabeli nie przestawiało podświetlenia na wiersz
o tych samych obrotach, ale z innego przebiegu (błąd zgłoszony przez użytkownika).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.logview import LogView  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402

SAMPLE = Path(__file__).resolve().parent / "data" / "przyklad.csv"


@pytest.fixture(scope="module")
def app():
    from vcds_viewer.qt import QtWidgets

    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    yield instance


@pytest.fixture(scope="module")
def log():
    if not SAMPLE.exists():
        pytest.skip("brak pliku przykładowego")
    return parse_log(SAMPLE)


def _view(app, log):
    view = LogView(log, DARK)
    view.resize(1400, 800)
    view.ensurePolished()
    return view


def test_time_axis_click_highlights_clicked_row(app, log):
    view = _view(app, log)
    view.cmb_x.setCurrentIndex(0)               # oś czasu
    group = log.groups[0]
    row = min(30, len(group.t) - 1)
    t = float(group.t[row])
    view.set_cursor_time(t)
    assert view.chart.cursor_x() == pytest.approx(t, abs=1e-6)
    assert view.table.model.hover_rows.get(group.letter) == row


def test_rpm_axis_click_keeps_time_of_clicked_row(app, log):
    """Kluczowy przypadek: przy osi obrotów czas musi zostać ten, w który kliknięto."""
    view = _view(app, log)
    view.cmb_x.setCurrentIndex(1)               # oś obrotów
    group = log.groups[1]
    row = min(40, len(group.t) - 1)
    t = float(group.t[row])
    expected_rpm = log.rpm_at(t)
    view.set_cursor_time(t)

    # kursor stoi na obrotach z tego wiersza...
    assert view.chart.cursor_x() == pytest.approx(expected_rpm, rel=0.02)
    # ...a podświetlony wiersz to nadal wiersz, w który kliknięto
    assert view.table.model.hover_rows.get(group.letter) == row


def test_rpm_axis_cursor_is_scrolled_into_view(app, log):
    """Kursor poza oglądanym zakresem nie może zniknąć z ekranu."""
    view = _view(app, log)
    view.cmb_x.setCurrentIndex(1)
    view.chart.fit()
    lo, hi = view.chart.plot.vb.viewRange()[0]
    span = hi - lo
    # celowo zwężamy widok do środka zakresu
    view.chart.plot.vb.setXRange(lo + span * 0.4, lo + span * 0.6, padding=0.0)
    group = log.groups[1]
    t = float(group.t[-1])                  # skrajny wiersz — duże obroty
    view.set_cursor_time(t)
    lo2, hi2 = view.chart.plot.vb.viewRange()[0]
    x = view.chart.cursor_x()
    assert lo2 <= x <= hi2, "kursor musi pozostać w widocznym zakresie osi X"


def test_arrow_keys_keep_cursor_in_view(app, log):
    """Przy przybliżeniu strzałki nie mogą wyprowadzić kursora za ekran."""
    view = _view(app, log)
    view.cmb_x.setCurrentIndex(0)                 # oś czasu
    view.chart.fit()
    lo, hi = view.chart.plot.vb.viewRange()[0]
    span = hi - lo
    # przybliżamy do 10% zakresu i stawiamy kursor na początku widoku
    view.chart.plot.vb.setXRange(lo, lo + span * 0.1, padding=0.0)
    view.set_cursor_time(float(lo) + span * 0.02)
    for _ in range(25):
        view.chart.step_cursor(1)
        lo2, hi2 = view.chart.plot.vb.viewRange()[0]
        assert lo2 <= view.chart.cursor_x() <= hi2, "kursor wyjechał poza widok"


def test_arrow_keys_keep_cursor_in_view_rpm(app, log):
    """To samo przy osi obrotów."""
    view = _view(app, log)
    view.cmb_x.setCurrentIndex(1)
    view.chart.fit()
    lo, hi = view.chart.plot.vb.viewRange()[0]
    span = hi - lo
    view.chart.plot.vb.setXRange(lo, lo + span * 0.1, padding=0.0)
    view.chart.set_cursor_x(float(lo) + span * 0.02, emit=True, snap=False)
    for _ in range(25):
        view.chart.step_cursor(1)
        lo2, hi2 = view.chart.plot.vb.viewRange()[0]
        assert lo2 <= view.chart.cursor_x() <= hi2, "kursor wyjechał poza widok"


def test_status_time_matches_clicked_row(app, log):
    """Pasek statusu nie może pokazywać innego czasu niż kliknięty wiersz."""
    view = _view(app, log)
    view.cmb_x.setCurrentIndex(1)
    seen: list[float] = []
    view.cursorMoved.connect(lambda t, rpm, src: seen.append(t))
    group = log.groups[1]
    row = min(35, len(group.t) - 1)
    t = float(group.t[row])
    view.set_cursor_time(t)
    assert seen and seen[-1] == pytest.approx(t, abs=1e-6)
