"""Testy rozcinania linii przy osi obrotów (żeby nie było „ścian” i pętli).

Sortowanie próbek po obrotach zestawia ze sobą punkty z odległych momentów logu
(np. dwa biegi jałowe albo koniec i początek przejazdu). Połączenie ich linią dawało
pionowe ściany, których w rzeczywistości nie było — linia musi się tam rozcinać.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.model import X_RPM, LogData  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402

SAMPLE = Path(__file__).resolve().parent / "data" / "przyklad.csv"


@pytest.fixture(scope="module")
def log():
    if not SAMPLE.exists():
        pytest.skip("brak pliku przykładowego")
    return parse_log(SAMPLE)


def _runs(x: np.ndarray, y: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Dzieli narysowaną serię na odcinki rozdzielone przerwami (NaN)."""
    out, start = [], 0
    for i in range(len(y) + 1):
        if i == len(y) or not np.isfinite(y[i]):
            if i > start:
                out.append((x[start:i], y[start:i]))
            start = i + 1
    return out


def test_no_backward_steps_within_run(log):
    """W obrębie jednego odcinka obroty nigdy nie cofają się — czyli nie ma pętli."""
    channel = log.find((("obciążenie"), ("%"), 0))
    x, y = log.plot_xy(channel, X_RPM, split_sweeps=True)
    runs = _runs(x, y)
    assert runs, "seria nie może być pusta"
    for xs, _ys in runs:
        if len(xs) < 2:
            continue
        assert np.all(np.diff(xs) >= -1e-9), "linia nie może się cofać po obrotach"


def test_line_is_broken_when_samples_are_far_apart_in_time(log):
    """Odcinki nie mogą łączyć próbek z odległych momentów logu.

    Sprawdzamy na danych z logu: dla każdego odcinka bierzemy czasy próbek i pilnujemy,
    żeby żadne dwie sąsiednie próbki w rysowaniu nie były dalej niż próg.
    """
    channel = log.find((("obciążenie"), ("%"), 0))
    t = np.asarray(channel.t, dtype=float)
    x_all = np.asarray(log.x_for(channel, X_RPM), dtype=float)
    x, y = log.plot_xy(channel, X_RPM, split_sweeps=True)
    limit = LogData._gap_limit(t)

    # pary (obroty, czas) posortowane tak, jak trafiają na wykres w obrębie odcinków
    pairs = sorted(zip(x_all.tolist(), t.tolist()))
    # dla każdej pary w narysowanej serii sprawdzamy najbliższy czas spośród próbek o tym x
    by_x: dict[float, list[float]] = {}
    for xi, ti in pairs:
        by_x.setdefault(round(xi, 6), []).append(ti)

    checked = 0
    for xs, _ys in _runs(x, y):
        for a, b in zip(xs, xs[1:]):
            ta = by_x.get(round(float(a), 6), [])
            tb = by_x.get(round(float(b), 6), [])
            if not ta or not tb:
                continue
            checked += 1
            # jeśli istnieje para próbek o tych obrotach blisko w czasie, połączenie jest prawdziwe
            close = any(abs(x1 - x2) <= limit for x1 in ta for x2 in tb)
            assert close, f"połączenie {a:.0f}→{b:.0f} obr/min łączy odległe momenty"
    assert checked > 10


def test_insert_gaps_splits_long_time_jumps():
    """Funkcja rozcinająca: skok czasu powyżej progu przerywa linię."""
    x = np.array([1000.0, 1100.0, 1200.0, 1300.0])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    t = np.array([0.0, 0.9, 50.0, 50.9])
    xs, ys = LogData._insert_gaps(x, y, t, limit=3.0)
    assert np.isnan(xs).sum() == 1
    runs = _runs(xs, ys)
    assert len(runs) == 2
    assert list(runs[0][0]) == [1000.0, 1100.0]
    assert list(runs[1][0]) == [1200.0, 1300.0]


def test_insert_gaps_keeps_continuous_data():
    """Bez skoków czasu linia zostaje w jednym kawałku."""
    x = np.linspace(1000.0, 6000.0, 40)
    y = np.sin(x / 1000.0)
    t = np.arange(40) * 0.9
    xs, ys = LogData._insert_gaps(x, y, t, limit=3.0)
    assert not np.isnan(xs).any()
    assert len(_runs(xs, ys)) == 1


def test_time_mode_is_untouched(log):
    """Przy osi czasu linia zostaje ciągła — rozcinanie dotyczy tylko osi obrotów."""
    channel = log.find((("obciążenie"), ("%"), 0))
    x, y = log.plot_xy(channel, "time", split_sweeps=True)
    assert len(x) == len(np.asarray(channel.t, dtype=float))
    assert not np.isnan(y).any()
