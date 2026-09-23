"""Testy logów z różną liczbą grup (1, 2 i 3) — parser wykrywa je dynamicznie."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.model import X_RPM
from vcds_viewer.parser import parse_log

TWO_GROUPS = """Wtorek,22,Wrzesień,2026,12:00:00:00009-VCID:0000000000000000-0000,Wersja VCDS: AKP 21.3.0,Wersja danych: 20240813 DS356.3
1K0 907 115 A,,2.0T,

,Grupa A:,'002,,,,Grupa B:,'011
,,Obroty silnika,Obciążenie,Czas wtrysku,Masowe n.przepływu,,Obroty silnika,Temperatura,Temperatura,Kąt w.zapłonu
,CZAS,,,,,CZAS,,,,
Znacznik,ZAPISU, /min, %, ms, g/s,ZAPISU, /min,*C,*C, *PGMP
,0.00,800,15.0,2.00,4.00,0.10,800,84.0,30.0,5.0
,1.00,1500,30.0,4.00,10.00,1.10,1500,85.0,31.0,8.0
,2.00,3000,80.0,10.00,40.00,2.10,3000,90.0,35.0,12.0
"""

ONE_GROUP = """Wtorek,22,Wrzesień,2026,12:00:00:00009-VCID:0000000000000000-0000,Wersja VCDS: AKP 21.3.0,Wersja danych: 20240813 DS356.3
1K0 907 115 A,,2.0T,

,Grupa A:,'002
,,Obroty silnika,Obciążenie,Czas wtrysku,Masowe n.przepływu
,CZAS,,,,
Znacznik,ZAPISU, /min, %, ms, g/s
,0.00,800,15.0,2.00,4.00
,1.00,1500,30.0,4.00,10.00
"""


def _write(tmp_path, text, name="log.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="cp1250")
    return p


def test_two_groups(tmp_path):
    log = parse_log(_write(tmp_path, TWO_GROUPS))
    assert [g.letter for g in log.groups] == ["A", "B"]
    assert [g.group_id for g in log.groups] == ["002", "011"]
    assert all(g.n_samples == 3 for g in log.groups)
    assert len(log.numeric_channels) == 8

    rpm = log.find(("obroty silnika", "/min", 0))
    load = log.find(("obciążenie", "%", 0))
    temp = log.find(("temperatura", "°c", 0))
    assert rpm.y[-1] == 3000 and load.y[-1] == 80.0
    assert temp.y[0] == 84.0
    assert rpm.group == "A" and temp.group == "B"

    # obroty są w obu grupach — wspólna seria RPM do osi X
    rt, ry = log.rpm_series()
    assert len(rt) == 6 and float(np.nanmax(ry)) == 3000

    # oś RPM działa dla parametru z grupy, która sama nie ma obrotów
    x = log.x_for(temp, X_RPM)
    assert np.allclose(x, [800, 1500, 3000])


def test_two_groups_compare_with_three_groups(tmp_path):
    """Log 2-grupowy porównuje się z 3-grupowym po wspólnych parametrach."""
    three = parse_log(Path(__file__).resolve().parent / "data" / "przyklad.csv")
    two = parse_log(_write(tmp_path, TWO_GROUPS))
    # wspólne klucze: tylko te same nazwy+jednostki+wystąpienia
    common = two.common_keys(three)
    assert ("obroty silnika", "/min", 0) in common
    assert ("temperatura", "°c", 0) in common
    assert all(two.find(k) is not None and three.find(k) is not None for k in common)


def test_one_group(tmp_path):
    log = parse_log(_write(tmp_path, ONE_GROUP))
    assert len(log.groups) == 1
    assert log.groups[0].group_id == "002"
    assert len(log.numeric_channels) == 4
    rt, _ = log.rpm_series()
    assert len(rt) == 2
