"""Statystyki dla zaznaczonego fragmentu wykresu (min / średnia / max).

Zgłoszenie: „zaznaczam myszą kawałek przejazdu i widzę min/max/średnią tylko dla niego”.
Testy pilnują trzech rzeczy: że liczby liczą się wyłącznie z zaznaczonych próbek,
że zaznaczenie da się tworzyć i przesuwać myszą oraz że panel pokazuje się i znika.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.logview import LogView  # noqa: E402
from vcds_viewer.model import X_RPM, X_TIME  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402

SAMPLE = Path(__file__).resolve().parent / "data" / "przyklad.csv"


class FakeDrag:
    """Minimalne zdarzenie przeciągnięcia — to, czego używa ViewBox i LogViewBox."""

    def __init__(self, box, x_from: float, x_to: float, *, start: bool, finish: bool = False):
        from vcds_viewer.qt import QtCore

        y = 0.0
        self._down = box.mapViewToScene(QtCore.QPointF(x_from, y))
        self._pos = box.mapViewToScene(QtCore.QPointF(x_to, y))
        self._local_from = QtCore.QPointF(x_from, y)
        self._local_to = QtCore.QPointF(x_to, y)
        self._start = start
        self._finish = finish
        self.accepted = False

    # --- to, czego potrzebuje LogViewBox
    def button(self):
        from vcds_viewer.qt import Qt

        return Qt.LeftButton

    def scenePos(self):                     # noqa: N802 (API pyqtgraph)
        return self._pos

    def buttonDownScenePos(self):           # noqa: N802
        return self._down

    def isStart(self):                      # noqa: N802
        return self._start

    def isFinish(self):                     # noqa: N802
        return self._finish

    def accept(self):
        self.accepted = True

    # --- a to, czego potrzebuje pyqtgraph przy zwykłym przesuwaniu wykresu
    def pos(self):
        return self._local_to

    def lastPos(self):                      # noqa: N802
        return self._local_from

    def buttonDownPos(self):                # noqa: N802
        return self._local_from

    def lastScenePos(self):                 # noqa: N802
        return self._down

    def screenPos(self):                    # noqa: N802
        return self._local_to

    def buttonDownScreenPos(self):          # noqa: N802
        return self._local_from

    def lastScreenPos(self):                # noqa: N802
        return self._local_from

    def buttons(self):
        from vcds_viewer.qt import Qt

        return Qt.LeftButton

    def modifiers(self):
        from vcds_viewer.qt import Qt

        return Qt.NoModifier

    def isAccepted(self):                   # noqa: N802
        return self.accepted

    def ignore(self):
        self.accepted = False


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


@pytest.fixture(scope="module")
def view(app, log):
    v = LogView(log, DARK)
    v.resize(1400, 860)
    v.ensurePolished()
    v.chart.fit()
    from vcds_viewer.qt import QtWidgets

    QtWidgets.QApplication.processEvents()
    return v


# ------------------------------------------------------------------ same liczby
def test_stats_count_only_samples_inside_range(log):
    ch = log.find((("obciążenie"), ("%"), 0))
    n, lo, hi, mean = log.stats_in_range(ch, X_TIME, 10.0, 20.0)
    t = np.asarray(ch.t, dtype=float)
    y = np.asarray(ch.y, dtype=float)
    mask = (t >= 10.0) & (t <= 20.0) & np.isfinite(y)
    assert n == int(mask.sum()) > 0
    assert lo == pytest.approx(float(y[mask].min()))
    assert hi == pytest.approx(float(y[mask].max()))
    assert mean == pytest.approx(float(y[mask].mean()))


def test_stats_are_narrower_than_whole_log(log):
    """Fragment musi dawać węższy zakres niż cały log — inaczej zaznaczenie nic nie zmienia."""
    ch = log.find((("obroty silnika"), ("/min"), 0))
    n_all, lo_all, hi_all, _ = log.stats_in_range(ch, X_TIME, -1e9, 1e9)
    n_part, lo_part, hi_part, _ = log.stats_in_range(ch, X_TIME, 10.0, 20.0)
    assert 0 < n_part < n_all
    assert (hi_part - lo_part) < (hi_all - lo_all)


def test_stats_on_rpm_axis_use_rpm_window(log):
    """Przy osi obrotów zakres znaczy „obroty od–do”, a nie czas."""
    ch = log.find((("obciążenie"), ("%"), 0))
    n, lo, hi, _ = log.stats_in_range(ch, X_RPM, 2000.0, 3000.0)
    x = np.asarray(log.x_for(ch, X_RPM), dtype=float)
    y = np.asarray(ch.y, dtype=float)
    mask = (x >= 2000.0) & (x <= 3000.0) & np.isfinite(y)
    assert n == int(mask.sum())
    assert lo == pytest.approx(float(y[mask].min()))


def test_empty_range_gives_zero_samples(log):
    ch = log.find((("obciążenie"), ("%"), 0))
    n, lo, hi, mean = log.stats_in_range(ch, X_TIME, 1e6, 2e6)
    assert n == 0
    assert np.isnan(lo) and np.isnan(hi) and np.isnan(mean)


# ------------------------------------------------------- zaznaczanie na wykresie
def test_drag_in_empty_area_creates_selection(view):
    view.chk_select.setChecked(True)
    vb = view.chart.vb
    vb.set_selection(None, None)
    vb.mouseDragEvent(FakeDrag(vb, 30.0, 30.0, start=True))
    vb.mouseDragEvent(FakeDrag(vb, 30.0, 45.0, start=False, finish=True))
    sel = view.chart.selection()
    assert sel is not None
    assert sel[0] == pytest.approx(30.0, abs=0.6)
    assert sel[1] == pytest.approx(45.0, abs=0.6)


def test_drag_near_edge_moves_only_that_edge(view):
    view.chk_select.setChecked(True)
    vb = view.chart.vb
    vb.set_selection(10.0, 20.0)
    vb.mouseDragEvent(FakeDrag(vb, 10.05, 10.05, start=True))     # przy lewej krawędzi
    vb.mouseDragEvent(FakeDrag(vb, 10.05, 6.0, start=False, finish=True))
    sel = view.chart.selection()
    assert sel[0] == pytest.approx(6.0, abs=0.6)
    assert sel[1] == pytest.approx(20.0, abs=0.3)


def test_drag_inside_moves_whole_selection(view):
    view.chk_select.setChecked(True)
    vb = view.chart.vb
    vb.set_selection(10.0, 20.0)
    vb.mouseDragEvent(FakeDrag(vb, 15.0, 15.0, start=True))       # środek pasma
    vb.mouseDragEvent(FakeDrag(vb, 15.0, 18.0, start=False, finish=True))
    sel = view.chart.selection()
    assert sel[0] == pytest.approx(13.0, abs=0.6)
    assert sel[1] == pytest.approx(23.0, abs=0.6)


def test_normal_drag_still_pans_when_mode_off(view, monkeypatch):
    """Bez trybu zaznaczania przeciągnięcie idzie do pyqtgraph — czyli przesuwa wykres."""
    from pyqtgraph import ViewBox

    passed: list[object] = []
    monkeypatch.setattr(ViewBox, "mouseDragEvent",
                        lambda self, ev, axis=None: passed.append(ev))
    view.chk_select.setChecked(False)
    vb = view.chart.vb
    vb.mouseDragEvent(FakeDrag(vb, 30.0, 45.0, start=True))
    assert passed, "przesuwanie wykresu musi działać jak dotąd"
    assert vb.selection() is None, "bez trybu zaznaczania nic się nie zaznacza"


# ------------------------------------------------------------------- panel w UI
def test_panel_shows_stats_for_selection(view):
    view.chk_select.setChecked(True)
    view.chart.set_selection(10.0, 20.0)
    from vcds_viewer.qt import QtWidgets

    QtWidgets.QApplication.processEvents()
    assert not view.sel_stats.isHidden()
    title = view.sel_stats.lbl_title.text()
    assert "Zaznaczony fragment" in title
    assert "10,00" in title and "20,00" in title
    cards = [view.sel_stats.cards_layout.itemAt(i).widget()
             for i in range(view.sel_stats.cards_layout.count())]
    assert len(cards) >= 3
    assert any("śr." in c.text() for c in cards)


def test_panel_hides_when_selection_cleared(view):
    view.chk_select.setChecked(True)
    view.chart.set_selection(10.0, 20.0)
    view.sel_stats.btn_clear.click()
    from vcds_viewer.qt import QtWidgets

    QtWidgets.QApplication.processEvents()
    assert view.sel_stats.isHidden()
    assert view.chart.selection() is None


def test_changing_axis_clears_selection(view):
    view.chk_select.setChecked(True)
    view.chart.set_selection(10.0, 20.0)
    view.cmb_x.setCurrentIndex(1)                 # oś obrotów
    from vcds_viewer.qt import QtWidgets

    QtWidgets.QApplication.processEvents()
    assert view.chart.selection() is None, "po zmianie jednostek stare zaznaczenie traci sens"
    assert not view.sel_stats.isVisible()
    view.cmb_x.setCurrentIndex(0)
