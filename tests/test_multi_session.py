"""Plik z KILKOMA sesjami logowania w jednym CSV.

VCDS dopisuje kolejne nagrania do tego samego pliku (powtarzając nagłówek), a każda
sesja zaczyna „CZAS” od zera. Wcześniej wszystkie wiersze trafiały do jednej serii
z cofającym się czasem — wykres rysował „piły”, nakładał sesje na siebie, a przebiegi
przy osi obrotów mnożyły się bez sensu (u użytkownika: 123 przebiegi).

Teraz kolejna sesja jest przesuwana w czasie tuż za poprzednią (osobno dla każdej
grupy), więc oś czasu jest jedna i nigdy się nie cofa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.model import X_TIME, LogData  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402

# Nagłówek bloku VCDS (3 grupy: 020 / 002 / 011) — powtarzany przed każdą sesją.
BLOK = """Poniedziałek,1,Wrzesień,2026,10:0{minute}:00:00009-VCID:60CF1587E043AA8BA3-5178,Wersja VCDS: AKP 21.3.0,Wersja danych: 20260601 DS375.1,,,,,,,,,
4B0 906 018 AA,,1.8L R4/5VT         0001,,,,,,,,,,,,,
,,,,,,,,,,,,,,,
,Grupa A:,020,,,,Grupa B:,002,,,,Grupa C:,011,,,
,,Stab.b.jałowego,Stab.b.jałowego,Stab.b.jałowego,Stab.b.jałowego,,Obroty silnika,Obciążenie,Czas wtrysku,Masowe n.przepływu,,Obroty silnika,Temperatura,Temperatura,Kąt w.zapłonu
,CZAS,,,,,CZAS,,,,,CZAS,,,,
Znacznik,ZAPISU,*KW,*KW,*KW,*KW,ZAPISU,/min,%,ms,g/s,ZAPISU,/min,*C,*C,*PGMP
"""


def _sesja(minute: str, first: float, rpm0: float) -> str:
    """Sesja: 5 wierszy; grupy A/B/C mają własne, bliskie sobie czasy."""
    rows = []
    for i in range(5):
        a = first + i
        b = first - 0.1 + i
        c = first - 0.2 + i
        rpm = rpm0 + 40 * i
        rows.append(
            f",{a:.2f},0,0,0,0,{b:.2f},{rpm:.0f},15,1.64,3.31,{c:.2f},{rpm - 20:.0f},83,39,4.5"
        )
    return BLOK.format(minute=minute) + "\n".join(rows) + "\n"


def _zrob_plik(tmp_path: Path) -> Path:
    p = tmp_path / "LOG-01-020-002-011.CSV"
    p.write_text(_sesja("0", first=0.6, rpm0=1000) + _sesja("5", first=0.2, rpm0=900),
                 encoding="utf-8")
    return p


def test_czasy_nie_cofaja_sie_miedzy_sesjami(tmp_path):
    """Każdy kanał: czas nigdy nie maleje — druga sesja startuje za pierwszą."""
    log = parse_log(_zrob_plik(tmp_path))
    for ch in log.channels:
        if not ch.has_data:
            continue
        t = np.asarray(ch.t, dtype=float)
        assert len(t) == 10, f"{ch.name}: oczekiwano 10 próbek, jest {len(t)}"
        assert np.all(np.diff(t) >= -1e-9), (
            f"{ch.name}: czasy się cofają — {np.min(np.diff(t)):.2f} s")


def test_wiersz_naglowka_nie_jest_probka(tmp_path):
    """Powtórzony nagłówek sesji („…VCID…”) nie może trafić na wykres jako próbka."""
    log = parse_log(_zrob_plik(tmp_path))
    for ch in log.channels:
        if not ch.has_data:
            continue
        raw = [r for r in ch.raw]
        assert all("VCID" not in r for r in raw), f"{ch.name}: nagłówek w próbkach"


def test_druga_sesja_jest_za_pierwsza_a_nie_nalozona(tmp_path):
    """Druga sesja jest przesunięta za pierwszą (maksimum > koniec pierwszej sesji)."""
    log = parse_log(_zrob_plik(tmp_path))
    ch = log.find((("obroty silnika"), ("/min"), 0))
    t = np.asarray(ch.t, dtype=float)
    # pierwsza sesja: 0.5..4.5; druga po przesunięciu: ~4.6.. — nic się nie nakłada
    assert t.max() > 8.0, "druga sesja powinna być przesunięta za pierwszą"
    assert t[5] >= t[4], "granica sesji nie może się cofać"
    # wartości obu sesji są zachowane (1000..1160 oraz 900..1060)
    y = np.asarray(ch.y, dtype=float)
    assert float(y[0]) == 1000.0 and float(y[5]) == 900.0


def test_rysowanie_czasu_ciagle_po_scaleniu_sesji(tmp_path):
    """Po scaleniu sesji linia przy osi czasu jest ciągła (bez przerw i cofnięć)."""
    log = parse_log(_zrob_plik(tmp_path))
    ch = log.find((("obroty silnika"), ("/min"), 0))
    x, y = log.plot_xy(ch, X_TIME)
    assert len(x) == 10
    assert not np.isnan(x).any(), "scalona oś czasu nie powinna mieć przerw"
    assert np.all(np.diff(x) >= -1e-9), "linia nie może się cofać w czasie"
