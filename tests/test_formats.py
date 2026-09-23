"""Testy odporności parsera na inne warianty eksportu VCDS."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.model import X_RPM
from vcds_viewer.parser import parse_log

EN_ONE_GROUP = """Tuesday,19,March,2024,12:00:00:12345-VCID:ABCDEF1234567890-1234,VCDS Version: Release 23.3.1,Data version: 20230421 DS346.2
7M0 906 018 XX,,1.8L R4/5VT G 0004,

,Group A:,'001,,,,Group B:,'002,,,,Group C:,'003
,,Engine Speed,Engine Load,Coolant Temp,Intake Air Temp,,Engine Speed,Injection,Injection,Ign. Timing,,Engine Speed,Mass Air,Throttle,Ign. Timing
,TIME,,,,,TIME,,,,,TIME,,,,
Marker,TIME, /min, %, *C, *C,TIME, /min, ms, ms, *BTDC,TIME, g/s, %, *BTDC
,0.00,800,15.0,90.0,30.0,0.10,800,2.00,1.50,5.0,0.20,4.0,2.0,3.0
,1.00,1200,25.5,91.0,31.0,1.10,1150,3.10,2.20,7.5,1.20,8.5,4.5,6.0
,2.00,2400,55.0,93.0,33.0,2.10,2380,6.20,4.40,12.0,2.20,22.0,12.0,9.0
"""

GERMAN_DECIMAL = """,Gruppe A:,'002,,,,,,,,
,,Drehzahl,Last,,,,,,,
,Zeit,,,,,,,,
Markierung,Zeit, /min, %,,,,,,,
,"0,00","800","15","5",,,,,,
,"1,50","1200","25","10",,,,,,
"""

ONE_GROUP_ONLY = """Wtorek,1,Styczeń,2026,10:00:00:00001-VCID:0000000000000000-0001,Wersja VCDS: AKP 21.3.0,Wersja danych: 20240813 DS356.3
1K0 907 115 A,,2.0T,

,Grupa A:,'001
,,Obroty silnika,Obciążenie,Temperatura,Kąt w.zapłonu
,CZAS,,,,
Znacznik,ZAPISU, /min, %, *C, *PGMP
,0.10,800,15.0,90.0,5.0
,1.10,1500,25.0,91.0,7.0
,2.10,3000,80.0,95.0,12.0
"""


def test_english_header(tmp_path):
    p = tmp_path / "en.csv"
    p.write_text(EN_ONE_GROUP, encoding="cp1250")
    log = parse_log(p)
    assert [g.group_id for g in log.groups] == ["001", "002", "003"]
    assert log.meta.ecu.startswith("7M0 906 018 XX")
    assert "Release 23.3.1" in log.meta.vcds_version
    speed = log.find(("engine speed", "/min", 0))
    assert speed is not None and speed.y[-1] == 2400
    temp = log.find(("coolant temp", "°c", 0))
    assert temp is not None and temp.unit == "°C"
    assert log.n_rows == 3


def test_single_group(tmp_path):
    p = tmp_path / "one.csv"
    p.write_text(ONE_GROUP_ONLY, encoding="cp1250")
    log = parse_log(p)
    assert len(log.groups) == 1
    assert log.groups[0].group_id == "001"
    assert len(log.numeric_channels) == 4
    assert log.duration == pytest.approx(2.0)
    rt, ry = log.rpm_series()
    assert len(rt) == 3
    # oś RPM działa też przy jednej grupie
    x = log.x_for(log.find(("obciążenie", "%", 0)), X_RPM)
    assert np.allclose(x, [800, 1500, 3000])


def test_german_decimal_comma_and_group_header(tmp_path):
    p = tmp_path / "de.csv"
    p.write_text(GERMAN_DECIMAL, encoding="cp1250")
    log = parse_log(p)
    assert log.groups[0].group_id == "002"
    rpm = log.find(("drehzahl", "/min", 0))
    assert rpm is not None and rpm.y[0] == 800


def test_file_without_data_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text(",Grupa A:,'001\n,,Obroty silnika\n,CZAS\nZnacznik,ZAPISU, /min\n", encoding="cp1250")
    with pytest.raises(ValueError):
        parse_log(p)


def test_file_without_header_raises(tmp_path):
    p = tmp_path / "plain.csv"
    p.write_text("a,b,c\n1,2,3\n", encoding="cp1250")
    with pytest.raises(ValueError):
        parse_log(p)
