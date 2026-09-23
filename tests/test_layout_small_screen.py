"""Testy układu okna — program musi działać na małych ekranach (laptopy warsztatowe).

Typowy laptop warsztatowy ma 1366x768. Wcześniej samo okno wymagało 1727 px szerokości
(pasek opcji w jednej linii), więc na takim ekranie tabela była ucięta.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.mainwindow import MainWindow  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.tableview import fit_column_widths  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402

SAMPLE = Path(__file__).resolve().parent / "data" / "przyklad.csv"
SMALL = (1366, 768)


@pytest.fixture(scope="module")
def app():
    from vcds_viewer.qt import QtWidgets

    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    yield instance


@pytest.fixture(scope="module")
def win(app):
    if not SAMPLE.exists():
        pytest.skip("brak pliku przykładowego")
    window = MainWindow()
    window.resize(*SMALL)
    window.open_path(str(SAMPLE))
    app.processEvents()
    window.grab()            # wymusza przeliczenie układu
    app.processEvents()
    yield window
    window.close()


def test_window_minimum_width_fits_small_screen(win):
    """Okno musi dać się zmieścić na ekranie 1366 px (z zapasem na pasek zadań)."""
    assert win.minimumSizeHint().width() <= 1200, win.minimumSizeHint().width()


def test_chart_toolbar_wraps(win):
    """Pasek opcji nad wykresem nie może wymuszać szerokości całego okna."""
    view = win.tabs.currentWidget()
    assert view.chart_toolbar.minimumSizeHint().width() <= 400


def test_table_columns_fit_without_horizontal_scroll(win):
    """Kolumny tabeli dopasowują się do szerokości okna."""
    view = win.tabs.currentWidget()
    table = view.table
    total = sum(table.view.columnWidth(i) for i in range(table.model.columnCount()))
    avail = table.view.viewport().width()
    assert avail > 0
    assert total <= avail + 4, f"kolumny {total} px w oknie {avail} px"


def test_column_fit_helper_scales_down_but_not_below_floor():
    """Funkcja dopasowania zwęża kolumny, ale nie poniżej wartości minimalnych."""

    class FakeView:
        class _Vp:
            def width(self_inner):
                return 400

        def viewport(self):
            return self._Vp()

    desired = [150] * 6          # 900 px przy dostępnych 400
    floors = [64] * 6            # minimum 384 px
    out = fit_column_widths(FakeView(), desired, floors)
    assert sum(out) <= 400
    assert all(w >= 64 for w in out)
    # gdy miejsca jest dość, szerokości zostają bez zmian
    assert fit_column_widths(FakeView(), [50] * 6, floors) == [50] * 6
