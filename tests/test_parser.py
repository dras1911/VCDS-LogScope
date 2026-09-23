"""Testy parsera i modelu danych VCDS."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.model import X_RPM, X_TIME, LogData
from vcds_viewer.parser import parse_log

SAMPLE = Path(__file__).resolve().parent / "data" / "przyklad.csv"


@pytest.fixture(scope="module")
def log() -> LogData:
    return parse_log(SAMPLE)


def test_meta(log):
    assert "września" in log.meta.date and "2026" in log.meta.date
    assert log.meta.time == "12:00:00"
    assert "AKP 21.3.0" in log.meta.vcds_version
    assert log.meta.ecu.startswith("XXX 906 018 XX")
    assert "1.8L R4/5VT" in log.meta.engine
    assert log.meta.summary().startswith("wtorek, 22 września 2026")


def test_color_map_is_unique(log):
    from vcds_viewer.colors import color_map

    colors = color_map(log.channels)
    assert len(colors) == len(log.numeric_channels)
    assert len(set(colors.values())) == len(colors)      # każda seria ma inny kolor
    assert colors[log.find(("obroty silnika", "/min", 0)).match_key] == "#e8d44d"


def test_groups(log):
    assert [g.letter for g in log.groups] == ["A", "B", "C"]
    assert [g.group_id for g in log.groups] == ["031", "002", "011"]
    assert all(g.n_samples == 78 for g in log.groups)


def test_channels(log):
    names = {(c.group, c.name): c.unit for c in log.channels}
    assert names[("A", "Napięcie")] == "V"
    assert names[("B", "Obroty silnika")] == "/min"
    assert names[("B", "Obciążenie")] == "%"
    assert names[("B", "Czas wtrysku")] == "ms"
    assert names[("B", "Masowe n.przepływu")] == "g/s"
    assert names[("C", "Kąt w.zapłonu")] == "°PGMP"
    temps = [c for c in log.channels if c.group == "C" and c.name == "Temperatura"]
    assert len(temps) == 2
    assert temps[0].occurrence == 0 and temps[1].occurrence == 1


def test_empty_binary_columns_dropped(log):
    # w tym logu kolumny „Bity binarnie” są całkowicie puste — nie zaśmiecają widoku
    assert not [c for c in log.channels if c.name == "Bity binarnie"]


def test_binary_column_with_data_is_text(tmp_path):
    from vcds_viewer.parser import read_text

    lines = read_text(SAMPLE).split("\n")
    for i in range(7, len(lines)):
        fields = lines[i].split(",")
        if len(fields) > 5:
            fields[3] = "1 0 1 0 0 0 1 0"
            lines[i] = ",".join(fields)
    p = tmp_path / "bin.csv"
    p.write_text("\n".join(lines), encoding="cp1250")
    log = parse_log(p)
    bits = [c for c in log.channels if c.name == "Bity binarnie"]
    assert len(bits) == 1
    assert not bits[0].numeric and not bits[0].has_data
    assert bits[0].raw[0] == "1 0 1 0 0 0 1 0"


def test_values(log):
    rpm = log.find((("obroty silnika"), ("/min"), 0))
    assert rpm is not None
    assert rpm.y[0] == 1560 and rpm.y[-1] == 3040
    assert rpm.t[0] == 0.60 and abs(rpm.t[-1] - 69.87) < 1e-6
    load = log.find((("obciążenie"), ("%"), 0))
    assert float(np.nanmax(load.y)) == pytest.approx(161.7)
    assert log.n_rows == 78
    assert log.duration == pytest.approx(69.87)


def test_rpm_series_and_axis(log):
    rt, ry = log.rpm_series()
    assert len(rt) == len(ry) > 78          # połączone grupy B i C
    assert np.all(np.diff(rt) >= 0)         # rosnące czasy
    voltage = log.find((("napięcie"), ("v"), 0))
    assert np.allclose(log.x_for(voltage, X_TIME), voltage.t)
    x_rpm = log.x_for(voltage, X_RPM)
    assert len(x_rpm) == len(voltage.t)
    assert 1000 < float(np.nanmax(x_rpm)) < 7000


def test_match_index_and_common_keys(log):
    other = parse_log(SAMPLE)
    keys = log.common_keys(other)
    assert len(keys) == len(log.numeric_channels)
    assert keys[0] in log.match_index()


def test_value_at(log):
    rpm = log.find((("obroty silnika"), ("/min"), 0))
    assert rpm.value_at(0.60) == 1560
    assert rpm.value_at(0.61) == 1560
    assert rpm.value_at(0.0) == 1560        # przed zakresem -> pierwsza próbka
