"""Etykiety osi: obroty to liczba całkowita, czas z miejscami po przecinku.

Zgłoszenie: przy osi obrotów w etykiecie kursora i w dymku widniało „3 200,00 obr/min”
oraz „Obroty = 3 200,000 obr/min” — obroty silnika to wartość całkowita, więc miejsca
po przecinku tylko zaśmiecają odczyt.
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
    return parse_log(SAMPLE)


@pytest.fixture(scope="module")
def view(app, log):
    v = LogView(log, DARK)
    v.resize(1200, 700)
    v.ensurePolished()
    return v


def test_rpm_axis_value_is_whole_number(view):
    """Oś obrotów: 3 200 obr/min, bez miejsc po przecinku."""
    view.cmb_x.setCurrentIndex(1)                     # Obroty [obr/min]
    chart = view.chart
    assert chart._fmt_x(3200.0) == "3\u00a0200"
    assert chart._badge_text(3200.0).startswith("3\u00a0200 obr/min")
    assert "," not in chart._fmt_x(4640.0).split(" ")[0]


def test_time_axis_value_keeps_decimals(view):
    """Oś czasu: bez zmian — 30,00 s (setne sekundy są potrzebne)."""
    view.cmb_x.setCurrentIndex(0)                     # Czas [s]
    chart = view.chart
    assert chart._fmt_x(30.0) == "30,00"
    assert chart._fmt_x(1.2345, 3) == "1,234"
    assert chart._badge_text(30.0).startswith("30,00 s")


def test_tooltip_header_uses_same_format(view):
    """Nagłówek dymku formatuje wartość osi tak samo jak etykieta."""
    chart = view.chart
    view.cmb_x.setCurrentIndex(1)                     # Obroty [obr/min]
    chart._build_tooltip(3200.0, [])
    text = chart.tooltip.text()
    assert "Obroty = <b>3\u00a0200</b> obr/min" in text
    assert "3\u00a0200,000" not in text

    view.cmb_x.setCurrentIndex(0)                     # Czas [s]
    chart._build_tooltip(30.0, [])
    assert "Czas = <b>30,000</b> s" in chart.tooltip.text()
