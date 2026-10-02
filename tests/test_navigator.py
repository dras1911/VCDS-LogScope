"""Suwaki nawigacji pod wykresem: powiększenie (zoom) i przesuwanie (pan).

Zgłoszenie użytkownika: „przydałby się suwak, żeby móc powiększyć wykres
i przesunąć do miejsca, gdzie potrzeba”. Testy pilnują, że:
* suwak powiększenia przybliża i oddala wykres w poziomie,
* suwak widoku przesuwa oglądany fragment i nie wypuszcza go za dane,
* oba suwaki odzwierciedlają stan wykresu także po rolce / przyciskach / „Dopasuj”,
* przebudowa serii (zmiana parametrów, rysowania) nie zrzuca przybliżenia,
  a zmiana osi X — zrzuca (tam już nie ma czego pokazywać),
* przełączenie „Nakładany/Pasma” przenosi oglądany fragment na drugi wykres.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.bandview import BandsChart  # noqa: E402
from vcds_viewer.chartview import LogChart, SeriesSpec  # noqa: E402
from vcds_viewer.logview import LogView  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402

SAMPLE = Path(__file__).resolve().parent / "data" / "przyklad.csv"
DOMAIN = 100.0          # syntetyczne serie: x od 0 do 100


@pytest.fixture(scope="module")
def app():
    from vcds_viewer.qt import QtWidgets

    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    yield instance


def _series(n: int = 200) -> list[SeriesSpec]:
    x = np.linspace(0.0, DOMAIN, n)
    y1 = np.sin(x / 10.0) * 50 + 60
    y2 = np.cos(x / 8.0) * 20 + 30
    return [
        SeriesSpec(sid="a", label="A", short="A", unit="", color="#4c8df6", x=x, y=y1),
        SeriesSpec(sid="b", label="B", short="B", unit="", color="#e5484d", x=x, y=y2),
    ]


def _chart(app) -> LogChart:
    c = LogChart(DARK)
    c.resize(900, 500)
    c.set_series(_series())
    app.processEvents()
    return c


def _span(widget) -> float:
    lo, hi = widget.vb.viewRange()[0]
    return hi - lo


def _first_lane_span(bands: BandsChart) -> float:
    lo, hi = bands._first_vb().viewRange()[0]
    return hi - lo


# ------------------------------------------------------------- suwak powiększenia
def test_zoom_slider_zooms_around_center(app):
    c = _chart(app)
    span0 = _span(c)
    c.nav.zoom.setValue(c.nav.ZOOM_STEPS // 2)
    app.processEvents()
    span1 = _span(c)
    assert span1 < span0
    expected = DOMAIN / math.sqrt(c.nav.MAX_ZOOM)
    assert span1 == pytest.approx(expected, rel=0.03)
    center = sum(c.vb.viewRange()[0]) / 2
    assert center == pytest.approx(50.0, abs=1.0)


def test_zoom_slider_back_to_full(app):
    c = _chart(app)
    c.nav.zoom.setValue(500)
    app.processEvents()
    c.nav.zoom.setValue(0)
    app.processEvents()
    assert _span(c) == pytest.approx(DOMAIN, rel=0.01)


def test_zoom_slider_matches_wheel_state(app):
    """Rolka/przyciski zmieniają widok — suwak powiększenia musi to pokazać."""
    c = _chart(app)
    c.vb.setXRange(40.0, 60.0, padding=0.0)
    app.processEvents()
    assert c.nav.zoom.value() > 0
    expected = math.log(DOMAIN / 20.0) / math.log(c.nav.MAX_ZOOM) * c.nav.ZOOM_STEPS
    assert c.nav.zoom.value() == pytest.approx(expected, abs=3)


def test_fit_resets_zoom_slider(app):
    c = _chart(app)
    c.nav.zoom.setValue(600)
    app.processEvents()
    c.fit()
    app.processEvents()
    assert c.nav.zoom.value() == 0


# -------------------------------------------------------------- suwak przesuwania
def test_scrollbar_pans_without_changing_zoom(app):
    c = _chart(app)
    c.nav.zoom.setValue(400)
    app.processEvents()
    lo0, hi0 = c.vb.viewRange()[0]
    c.nav.scroll.setValue(c.nav.scroll.maximum())      # skrajnie w prawo
    app.processEvents()
    lo1, hi1 = c.vb.viewRange()[0]
    assert lo1 > lo0                       # widok pojechał w prawo
    assert hi1 == pytest.approx(DOMAIN, abs=0.5)        # do końca logu
    assert (hi1 - lo1) == pytest.approx(hi0 - lo0, rel=0.02)   # bez zmiany przybliżenia


def test_scrollbar_clamps_at_edges(app):
    c = _chart(app)
    c.nav.zoom.setValue(300)
    app.processEvents()
    c.nav.scroll.setValue(c.nav.scroll.maximum())
    app.processEvents()
    lo, hi = c.vb.viewRange()[0]
    assert lo >= 0.0
    assert hi <= DOMAIN + 0.5              # koniec logu, ani o włos dalej


def test_scrollbar_reflects_view_changes(app):
    c = _chart(app)
    c.vb.setXRange(20.0, 40.0, padding=0.0)
    app.processEvents()
    assert c.nav.scroll.value() == pytest.approx(20.0 * c.nav.VALUE_SCALE, abs=2)


# --------------------------------------------------- stan nawigacji przy przebudowie
def test_series_rebuild_keeps_user_zoom(app):
    c = _chart(app)
    c.nav.zoom.setValue(300)
    app.processEvents()
    lo0, hi0 = c.vb.viewRange()[0]
    c.set_series(_series())                # np. przełączenie parametru
    app.processEvents()
    lo1, hi1 = c.vb.viewRange()[0]
    assert lo1 == pytest.approx(lo0, abs=0.05)
    assert (hi1 - lo1) == pytest.approx(hi0 - lo0, rel=0.02)


def test_axis_change_resets_zoom(app):
    c = _chart(app)
    c.nav.zoom.setValue(300)
    app.processEvents()
    c.set_x_axis("rpm", "obr/min", "Obroty silnika")   # inna jednostka osi X
    c.set_series(_series())
    app.processEvents()
    assert c.nav.zoom.value() == 0


def test_navigator_disabled_without_data(app):
    c = LogChart(DARK)
    c.resize(400, 300)
    app.processEvents()
    assert not c.nav.isEnabled()


# ------------------------------------------------------------- widok pasm
def test_bands_navigator_pans_and_zooms_all_lanes(app):
    b = BandsChart(DARK)
    b.resize(900, 600)
    b.set_series(_series())
    app.processEvents()
    vb = b._first_vb()
    lo0, hi0 = vb.viewRange()[0]
    b.nav.zoom.setValue(400)
    app.processEvents()
    lo1, hi1 = vb.viewRange()[0]
    assert (hi1 - lo1) < (hi0 - lo0)
    b.nav.scroll.setValue(b.nav.scroll.maximum())      # przesuwamy do końca logu
    app.processEvents()
    lo2, hi2 = vb.viewRange()[0]
    assert lo2 > lo1
    # wspólna oś X: każdy pas pokazuje ten sam fragment
    for lane in b.visible_lanes():
        if lane.plot is not None:
            lx0, lx1 = lane.plot.vb.viewRange()[0]
            assert lx0 == pytest.approx(lo2, abs=0.05)
            assert lx1 == pytest.approx(hi2, abs=0.05)


def test_bands_toolbar_zoom_is_single_step(app):
    """Przyciski − / + nie mogą mnożyć kroku przez liczbę pasów."""
    b = BandsChart(DARK)
    b.resize(900, 600)
    b.set_series(_series())
    app.processEvents()
    span0 = _first_lane_span(b)
    b.zoom(0.5)
    app.processEvents()
    span1 = _first_lane_span(b)
    assert span1 == pytest.approx(span0 * 0.5, rel=0.05)


# ------------------------------------------------- przełączanie widoków w LogView
def test_logview_switch_carries_view_range(app):
    if not SAMPLE.exists():
        pytest.skip("brak pliku przykładowego")
    log = parse_log(SAMPLE)
    view = LogView(log, DARK)
    view.resize(1400, 800)
    app.processEvents()

    view.chart.nav.zoom.setValue(400)      # przybliżamy w widoku nakładanym
    app.processEvents()
    lo_c, hi_c = view.chart.view_x_range()

    view.cmb_view.setCurrentIndex(1)       # -> pasma
    app.processEvents()
    lo_b, hi_b = view.bands.view_x_range()
    assert lo_b == pytest.approx(lo_c, abs=(hi_c - lo_c) * 0.05)
    assert (hi_b - lo_b) == pytest.approx(hi_c - lo_c, rel=0.05)

    view.bands.nav.scroll.setValue(view.bands.nav.scroll.maximum() // 2)
    app.processEvents()
    lo_b2, hi_b2 = view.bands.view_x_range()
    view.cmb_view.setCurrentIndex(0)       # -> z powrotem nakładany
    app.processEvents()
    lo_c2, hi_c2 = view.chart.view_x_range()
    assert lo_c2 == pytest.approx(lo_b2, abs=(hi_b2 - lo_b2) * 0.05)


# ---------------------------------------------------------- kontrakt samego widgetu
def test_navigator_signal_contract(app):
    from vcds_viewer.navigator import ChartNavigator

    nav = ChartNavigator()
    nav.set_domain(0.0, DOMAIN)
    nav.set_view(0.0, DOMAIN)
    seen: list[tuple[float, float]] = []
    nav.rangeRequested.connect(lambda a, b: seen.append((a, b)))

    nav.zoom.setValue(500)
    span = DOMAIN / math.sqrt(nav.MAX_ZOOM)
    assert seen[-1] == pytest.approx((50.0 - span / 2, 50.0 + span / 2), abs=0.02)

    nav.set_view(*seen[-1])                 # obieg: wykres potwierdza nowy zakres
    nav.scroll.setValue(nav.scroll.maximum())
    assert seen[-1][1] == pytest.approx(DOMAIN, abs=0.01)   # prawy brzeg bez przestrzelenia
