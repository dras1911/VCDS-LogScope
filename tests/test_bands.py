"""Testy widoku pasm (BandsChart) — budowa, kursor, widoczność, oś obrotów.

Testy działają bez okna (QT_QPA_PLATFORM=offscreen), ale wymagają instancji QApplication.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.bandview import BandsChart  # noqa: E402
from vcds_viewer.chartview import SeriesSpec  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402

SAMPLE = Path(__file__).resolve().parent / "data" / "przyklad.csv"


@pytest.fixture(scope="module")
def app():
    from vcds_viewer.qt import QtWidgets

    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    yield instance


def _specs(n: int = 3, unit: str = "V"):
    specs = []
    for i in range(n):
        x = np.linspace(0, 10, 21)
        y = np.sin(x / (i + 1)) * (i + 1)
        specs.append(
            SeriesSpec(
                sid=f"c{i}",
                label=f"Parametr {i} [{unit}] · Grupa A",
                short=f"Parametr {i} [{unit}]",
                unit=unit,
                color="#ff0000" if i % 2 == 0 else "#00ff00",
                x=x,
                y=y,
                group=f"Grupa {chr(65 + i)}",
            )
        )
    return specs


def test_lanes_created_per_series(app):
    chart = BandsChart(DARK)
    chart.set_series(_specs(4))
    assert len(chart._lanes) == 4
    assert len(chart.visible_lanes()) == 4


def test_cursor_snaps_to_sample_and_reports(app):
    chart = BandsChart(DARK)
    chart.set_series(_specs(2))
    chart.set_cursor_x(3.33)
    # przyciąganie do próbek: trafiamy w jedną z wartości z siatki 0..10 co 0.5
    grid = np.linspace(0, 10, 21)
    assert float(np.min(np.abs(grid - chart.cursor_x()))) < 1e-9


def test_step_cursor_moves_to_next_sample(app):
    chart = BandsChart(DARK)
    chart.set_series(_specs(1))
    chart.set_cursor_x(0.0, snap=False)
    chart.step_cursor(1)
    assert chart.cursor_x() > 0.0


def test_hidden_series_is_not_measured(app):
    chart = BandsChart(DARK)
    chart.set_series(_specs(3))
    chart.set_series_visible("c1", False)
    assert len(chart.visible_lanes()) == 2
    assert chart._lanes["c1"].plot.isVisible() is False


def test_cursor_value_matches_data(app):
    """Wartość pokazywana w nagłówku pasa musi pochodzić z danych tej serii."""
    chart = BandsChart(DARK)
    specs = _specs(1)
    chart.set_series(specs)
    chart.set_cursor_x(5.0, snap=False)
    lane = chart._lanes["c0"]
    i = int(np.argmin(np.abs(lane.lx - 5.0)))
    assert lane.ly[i] == pytest.approx(float(np.sin(5.0)))


def test_rpm_axis_hides_rpm_series(app):
    """Przy osi X = obroty seria obrotów nie jest rysowana jako pas."""
    if not SAMPLE.exists():
        pytest.skip("brak pliku przykładowego")
    log = parse_log(SAMPLE)
    chart = BandsChart(DARK)
    specs = []
    for ch in log.numeric_channels:
        x, y = log.plot_xy(ch, "rpm", split_sweeps=True)
        specs.append(SeriesSpec(sid=str(id(ch)), label=ch.label, short=ch.short_label,
                                unit=ch.unit, color="#888888", x=x, y=y, group=ch.group))
    chart.set_series(specs)
    assert len(chart._lanes) == len(specs)
    chart.set_x_axis("rpm", "obr/min", "Obroty silnika")
    chart.set_cursor_x(3000.0, snap=False)
    assert chart.cursor_x() == pytest.approx(3000.0)


def test_fit_uses_visible_data_only(app):
    chart = BandsChart(DARK)
    chart.set_series(_specs(3))
    chart.set_series_visible("c0", False)
    chart.fit()
    for sid in ("c1", "c2"):
        lane = chart._lanes[sid]
        rng = lane.plot.vb.viewRange()[1]
        assert rng[0] < lane.ymin + 1e-6
        assert rng[1] > lane.ymax - 1e-6
