"""Automatyczne dopasowanie logów w czasie + wybór logu bazowego w oknie porównania."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from vcds_viewer.compare import CompareView          # noqa: E402
from vcds_viewer.model import best_time_offset       # noqa: E402
from vcds_viewer.parser import parse_log             # noqa: E402
from vcds_viewer.theme import DARK                   # noqa: E402

SAMPLE = ROOT / "tests" / "data" / "przyklad.csv"


@pytest.fixture(scope="module")
def app():
    from vcds_viewer.qt import QtWidgets

    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    yield instance


def shifted(log, dt: float):
    """Kopia logu z przesuniętymi czasami — do sprawdzenia, czy dopasowanie to wykryje."""
    clone = parse_log(log.path)
    for g in clone.groups:
        g.t = [float(x) + dt for x in g.t]
    for c in clone.channels:
        c.t = [float(x) + dt for x in c.t]
    return clone


@pytest.fixture(scope="module")
def log():
    return parse_log(SAMPLE)


@pytest.mark.parametrize("dt", [1.1, -1.1, 3.0])
def test_best_time_offset_finds_known_shift(log, dt):
    """Dopasowanie musi znaleźć przesunięcie, które sami wprowadziliśmy (z dokładnością 0,15 s)."""
    other = shifted(log, dt)
    res = best_time_offset(log, other)
    assert res is not None, "dopasowanie nie zwróciło wyniku"
    off, score, contrast, used = res
    assert abs(off + dt) < 0.15, f"wykryto {off:+.2f} s, oczekiwano {-dt:+.2f} s"
    assert score > 0.9, f"zgodność powinna być wysoka dla tego samego przebiegu ({score:.2f})"
    assert used >= 3, "powinno być użyte kilka wspólnych parametrów"


def test_best_time_offset_zero_for_identical(log):
    """Ten sam log porównany sam ze sobą nie może być przesuwany."""
    res = best_time_offset(log, parse_log(SAMPLE))
    assert res is not None
    assert abs(res[0]) <= 0.05, f"przesunięcie {res[0]:+.2f} s dla identycznych logów"


def test_best_time_offset_none_without_common_params(log):
    """Bez wspólnych parametrów nie ma czego dopasowywać."""
    stripped = parse_log(SAMPLE)
    for ch in stripped.channels:
        ch.name = ch.name + " (inny sterownik)"
        ch.unit = ch.unit + "X"
    assert best_time_offset(log, stripped) is None


def test_compare_view_aligns_logs_on_open(app, log):
    """Okno porównania samo ustawia przesunięcie, gdy jeden log jest przesunięty w czasie."""
    other = shifted(log, 1.4)
    view = CompareView([log, other], DARK)
    assert abs(view.offset_b + 1.4) < 0.2, f"offset_b = {view.offset_b:+.2f} s"
    assert abs(view.spin_offset.value() - view.offset_b) < 1e-6
    assert "Dopasowano" in view.lbl_hint.text()
    view.deleteLater()


def test_compare_view_base_switch_changes_delta_sign(app, log):
    """Po zmianie logu bazowego różnice zmieniają znak, a nagłówki opisują nową bazę."""
    other = shifted(log, 0.0)
    view = CompareView([log, other], DARK)
    view.refresh()
    view._on_base(1)                       # bazą zostaje log B
    assert view.base == 1
    headers = [view.model.headerText(c) for c in range(view.model.columnCount())]
    assert any("Δ A−B" in h for h in headers), headers
    assert "− log B" in view.lbl_delta_hint.text()
    assert view.lbl_offset.text().startswith("Przesunięcie A")
    view.deleteLater()


def test_compare_view_base_switch_keeps_columns(app, log):
    """Zmiana bazy nie gubi kolumn i nie wywala tabeli."""
    view = CompareView([log, shifted(log, 0.5)], DARK)
    before = view.model.columnCount()
    view._on_base(1)
    after = view.model.columnCount()
    assert after == before
    for c in range(after):
        assert view.model.headerText(c)
    view.deleteLater()


def test_rpm_axis_switch_works_in_compare(app, log):
    """Przełączenie na oś obrotów musi działać (kiedyś wywalało się na _draw_touched)."""
    view = CompareView([log, shifted(log, 0.0)], DARK)
    assert view._draw_touched is False
    view.cmb_x.setCurrentIndex(1)          # Obroty [obr/min]
    assert view.x_mode == "rpm"
    assert view.cmb_draw.currentData() == "points", "przy obrotach domyślnie punkty"
    assert not view.btn_align.isEnabled(), "dopasowanie w czasie tylko przy osi czasu"
    assert not view.spin_offset.isEnabled()
    view.cmb_x.setCurrentIndex(0)          # powrót na czas
    assert view.btn_align.isEnabled()
    view.deleteLater()


def test_compare_view_with_three_logs(app, log):
    """Trzy logi: wybór bazy działa, a dopasowanie liczy się względem wybranej bazy."""
    logs = [log, shifted(log, 0.8), shifted(log, 1.6)]
    view = CompareView(logs, DARK)
    assert view.cmb_base.count() == 3
    view._on_base(2)                       # bazą jest log C
    assert view.base == 2
    headers = [view.model.headerText(c) for c in range(view.model.columnCount())]
    assert any("Δ A−C" in h for h in headers), headers
    assert view.lbl_offset.text().startswith("Przesunięcie A, B")
    view.deleteLater()


def test_offset_only_applied_to_non_base_log(app, log):
    """Przesunięcie dotyczy logu niebędącego bazą — baza zostaje na swoim miejscu."""
    view = CompareView([log, shifted(log, 1.0)], DARK)
    view.offset_b = 2.0
    view.refresh()
    prm = next(p for p in view.params if p.common)
    base_vals = prm.series[view.base]
    assert np.isfinite(base_vals).any()
    # wartość bazowa przy 5,0 s musi zgadzać się z oryginałem (baza nie jest przesuwana)
    grid = view.grid
    idx = int(np.argmin(np.abs(grid - 5.0)))
    ch = view.logs[view.base].find(prm.key)
    assert abs(base_vals[idx] - np.interp(5.0, np.asarray(ch.t, float),
                                          np.asarray(ch.y, float))) < 0.5
    view.deleteLater()
