"""Pionowe kreski przy osi obrotów: program ma tłumaczyć, że to prawdziwe dane.

Zgłoszenie: użytkownik zobaczył przy osi obrotów pionowe kreski i uznał je za błąd
(sklejone przebiegi). Program rozcina tylko pary próbek z odległych momentów, więc
skok mieszczący się w jednym kroku czasu jest prawdziwy (np. odcięcie wtrysku:
obciążenie 120% → 14%) — i podpowiedź powinna to powiedzieć.
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


def test_steep_jumps_are_found_in_real_log(log):
    """W logu przykładowym są prawdziwe skoki (odcięcie wtrysku) — i są policzone."""
    assert log.steep_jumps() >= 3


def test_steep_jumps_are_cached(log):
    """Liczba skoków liczy się raz (podpowiedź odświeża się przy każdym kliknięciu)."""
    assert log.steep_jumps() == log.steep_jumps()


def test_hint_explains_vertical_lines(app, log):
    """Przy osi obrotów w trybie „Linia” podpowiedź mówi, że kreski to prawdziwe dane."""
    view = LogView(log, DARK)
    view.resize(1200, 700)
    view.ensurePolished()
    view.cmb_x.setCurrentIndex(1)                 # Obroty [obr/min]
    view.cmb_draw.setCurrentIndex(0)              # Linia
    view.chk_sweeps.setChecked(True)
    from vcds_viewer.qt import QtWidgets

    QtWidgets.QApplication.processEvents()
    text = view.lbl_hint.text()
    assert "prawdziwe skoki danych" in text
    assert "odcięcie wtrysku" in text
    view.close()


def test_hint_silent_when_axis_is_time(app, log):
    """Przy osi czasu ta informacja nie ma sensu — nie może się pokazywać."""
    view = LogView(log, DARK)
    view.resize(1200, 700)
    view.ensurePolished()
    view.cmb_x.setCurrentIndex(0)                 # Czas [s]
    from vcds_viewer.qt import QtWidgets

    QtWidgets.QApplication.processEvents()
    assert "prawdziwe skoki danych" not in view.lbl_hint.text()
    view.close()
