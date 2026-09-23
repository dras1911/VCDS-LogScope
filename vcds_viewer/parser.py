"""Parser plików CSV generowanych przez VCDS (VAG-COM).

Obsługiwany format (polski i angielski VCDS):

    Wtorek,22,Wrzesień,2026,18:59:06:00009-VCID:...,Wersja VCDS: AKP 21.3.0,Wersja danych: ...
    4B0 906 018 AA,,1.8L R4/5VT         0001,
    <pusto>
    ,Grupa A:,'031,,,,Grupa B:,'002,,,,Grupa C:,'011
    ,,Napięcie,Bity binarnie,...,,Obroty silnika,Obciążenie,...
    ,CZAS,,,,,CZAS,,,,,CZAS,,,,
    Znacznik,ZAPISU, V,,,,ZAPISU, /min, %, ms, g/s,ZAPISU, /min,*C,*C, *PGMP
    ,0.30,0.005,        ,...,0.60,1560,13.5,0.00,4.06,0.00,1560,84.0,30.0,-2.3

Układ kolumn: 1 kolumna znacznika + dla każdej grupy 5 kolumn
(kolumna czasu + 4 kolumny wartości).
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Optional

import numpy as np

from .model import Channel, Group, LogData, LogMeta, clean_unit

# Kodowania spotykane w eksportach VCDS (CP1250 dla Windows PL).
_ENCODINGS = ("cp1250", "cp1252", "utf-8-sig", "utf-8", "latin-1")

_GROUP_RE = re.compile(r"^\s*(?:Grupa|Group|Gruppe)\s*([A-Za-z])\s*:\s*'?\s*(.*?)\s*'?\s*$", re.I)
_MARKER_RE = re.compile(r"^\s*(?:Znacznik|Marker|Markierung)\s*$", re.I)
_TIME_LABEL_RE = re.compile(r"^\s*(?:CZAS|TIME|Zeit|ZAPISU|ZAPIS|Timestamp)\s*$", re.I)
_VCID_RE = re.compile(r"VCID:([0-9A-Fa-f\-]+)")
_CLOCK_RE = re.compile(r"\b(\d{1,2}:\d{2}:\d{2})\b")
_VERSION_RE = re.compile(r"(?:Wersja\s+VCDS|VCDS[-\s]?Version|VCDS-Version)\s*:?\s*([^,]+)", re.I)
_DATA_VER_RE = re.compile(r"(?:Wersja\s+danych|Data\s+version|Datenstand)\s*:?\s*([^,]+)", re.I)
_NULLS = {"", "---", "--", "-", "n/a", "N/A", "?", "x", "X"}

# Polskie nazwy miesięcy w dopełniaczu („22 września 2026” zamiast „22 Wrzesień 2026”).
_MONTHS_PL = {
    "styczeń": "stycznia", "luty": "lutego", "marzec": "marca", "kwiecień": "kwietnia",
    "maj": "maja", "czerwiec": "czerwca", "lipiec": "lipca", "sierpień": "sierpnia",
    "wrzesień": "września", "październik": "października", "listopad": "listopada",
    "grudzień": "grudnia",
}


# --------------------------------------------------------------------------- IO
def read_text(path: str | Path) -> str:
    """Wczytuje plik logu z wykryciem kodowania (CP1250 itd.)."""
    data = Path(path).read_bytes()
    for enc in _ENCODINGS:
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - ostatnia deska ratunku
        text = data.decode("latin-1", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split(line: str) -> list[str]:
    """Dzieli linię CSV z obsługą cudzysłowów."""
    try:
        return next(csv.reader(io.StringIO(line)))
    except Exception:  # pragma: no cover
        return line.split(",")


def _num(value: str) -> Optional[float]:
    """Zamienia pole tekstowe na liczbę (obsługa przecinka dziesiętnego)."""
    if value is None:
        return None
    t = value.strip()
    if t in _NULLS:
        return None
    # dane binarne typu "1 0 0 1" traktujemy jako tekst, nie liczbę
    if len(t.split()) > 1:
        return None
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _pad(fields: list[str], size: int) -> list[str]:
    return fields + [""] * (size - len(fields)) if len(fields) < size else fields


# ------------------------------------------------------------------- nagłówek
def _parse_meta(lines: list[str], path: str) -> LogMeta:
    meta = LogMeta(source=path)
    head = lines[0] if lines else ""
    fields = [f.strip() for f in _split(head)]
    if len(fields) >= 4:
        meta.weekday = fields[0]
        try:
            day = int(fields[1])
            month = fields[2].strip()
            year = int(fields[3])
            month_pl = _MONTHS_PL.get(month.lower(), month)
            meta.date = f"{day:02d} {month_pl} {year}"
        except ValueError:
            meta.date = " ".join(fields[:4])
    clock = _CLOCK_RE.search(head)
    if clock:
        meta.time = clock.group(1)
    vcid = _VCID_RE.search(head)
    if vcid:
        meta.vcid = vcid.group(1)
    m = _VERSION_RE.search(head)
    if m:
        meta.vcds_version = m.group(1).strip()
    m = _DATA_VER_RE.search(head)
    if m:
        meta.data_version = m.group(1).strip()

    # druga linia: numer części sterownika + kod silnika
    if len(lines) > 1:
        f2 = _pad([f.strip() for f in _split(lines[1])], 4)
        meta.ecu = f2[0]
        meta.engine = f2[2].strip()
    return meta


def _find_header(lines: list[str]) -> tuple[int, list[tuple[int, str, str]]]:
    """Znajduje wiersz z opisem grup. Zwraca (indeks, [(kolumna, litera, nr grupy)])."""
    for i, line in enumerate(lines[:30]):
        fields = _split(line)
        found: list[tuple[int, str, str]] = []
        for j, f in enumerate(fields):
            m = _GROUP_RE.match(f)
            if not m:
                continue
            gid = m.group(2).strip().strip("'").strip()
            if not gid and j + 1 < len(fields):
                # w eksporcie VCDS numer grupy stoi w następnej kolumnie: "Grupa A:,'031"
                gid = fields[j + 1].strip().strip("'").strip()
            found.append((j, m.group(1).upper(), gid))
        if found:
            return i, found
    return -1, []


# --------------------------------------------------------------------- parser
def parse_log(path: str | Path) -> LogData:
    """Parsuje plik logu VCDS i zwraca model danych."""
    path = str(path)
    lines = [ln for ln in read_text(path).split("\n")]
    meta = _parse_meta(lines, path)

    group_row, groups_found = _find_header(lines)
    if group_row < 0:
        raise ValueError(
            "Nie rozpoznano nagłówka logu VCDS (brak wiersza 'Grupa A:' / 'Group A:')."
        )

    names_row = _pad(_split(lines[group_row + 1]) if group_row + 1 < len(lines) else [], 32)

    # wiersz z jednostkami: ten, który zaczyna się od 'Marker'/'Znacznik'
    units_row_idx = -1
    for k in range(group_row + 1, min(group_row + 6, len(lines))):
        f = _split(lines[k])
        if f and _MARKER_RE.match(f[0] or ""):
            units_row_idx = k
            break
    if units_row_idx < 0:
        units_row_idx = group_row + 2
    units_row = _pad(_split(lines[units_row_idx]) if units_row_idx < len(lines) else [], 32)

    # kolumny danych: 1 znacznik + 5 kolumn na każdą grupę
    starts = [col for col, _, _ in groups_found]
    width = max(max(starts) + 5, max(len(_split(l)) for l in lines[units_row_idx + 1: units_row_idx + 40] or [""]))

    # ------------------------------------------------------------------ grupy
    groups: list[Group] = []
    for col, letter, gid in groups_found:
        time_label = (units_row[col].strip() if col < len(units_row) else "") or "CZAS"
        if not _TIME_LABEL_RE.match(time_label):
            time_label = "CZAS"
        grp = Group(letter=letter, group_id=gid, time_label=time_label)
        for k in range(4):
            idx = col + 1 + k
            name = (names_row[idx].strip() if idx < len(names_row) else "")
            unit = clean_unit(units_row[idx] if idx < len(units_row) else "")
            grp.channels.append(
                Channel(name=name or f"Parametr {k + 1}", unit=unit, group=letter,
                        group_id=gid, t=np.array([]), y=None, raw=[], numeric=True)
            )
        groups.append(grp)

    # ------------------------------------------------------------------- dane
    times: dict[str, list[float]] = {g.letter: [] for g in groups}
    values: dict[tuple[str, int], list[Optional[float]]] = {
        (g.letter, k): [] for g in groups for k in range(4)
    }
    raws: dict[tuple[str, int], list[str]] = {
        (g.letter, k): [] for g in groups for k in range(4)
    }
    blocks = 1

    for line in lines[units_row_idx + 1:]:
        if not line.strip():
            continue
        fields = _pad(_split(line), width + 4)
        marker = (fields[0] or "").strip()
        row_time: dict[str, float] = {}
        for col, letter, _gid in groups_found:
            raw_t = (fields[col] or "").strip()
            if not raw_t or _TIME_LABEL_RE.match(raw_t) or _MARKER_RE.match(raw_t):
                continue  # brak próbki dla tej grupy / powtórzony nagłówek bloku
            t = _num(raw_t)
            if t is None:
                continue
            row_time[letter] = t
        if not row_time:
            continue
        if marker:
            # znacznik w kolumnie 1 = nowy blok logowania
            if any(times.values()):
                blocks += 1
            marker = ""
        for col, letter, _gid in groups_found:
            if letter not in row_time:
                continue
            times[letter].append(row_time[letter])
            for k in range(4):
                idx = col + 1 + k
                raw = (fields[idx] or "").strip() if idx < len(fields) else ""
                raws[(letter, k)].append(raw)
                values[(letter, k)].append(_num(raw))

    if not any(times.values()):
        raise ValueError("Plik nie zawiera wierszy danych (tylko nagłówek).")

    # --------------------------------------------------- kanały + statystyki
    occurrences: dict[tuple, int] = {}
    for grp in groups:
        grp.t = np.asarray(times[grp.letter], dtype=float)
        # numeracja powtórzonych nazw w obrębie grupy (np. 4× „Stab.b.jałowego”)
        dup_counts: dict[str, int] = {}
        for ch in grp.channels:
            key_name = ch.name.strip().lower()
            dup_counts[key_name] = dup_counts.get(key_name, 0) + 1
        seen: dict[str, int] = {}
        for k, ch in enumerate(grp.channels):
            vals = values[(grp.letter, k)]
            raw = raws[(grp.letter, k)]
            n_ok = sum(1 for v in vals if v is not None)
            n_any = sum(1 for r in raw if r)
            ch.raw = raw
            ch.t = grp.t
            key_name = ch.name.strip().lower()
            ch.dup_count = dup_counts.get(key_name, 1)
            ch.dup_index = seen.get(key_name, 0)
            seen[key_name] = ch.dup_index + 1
            if n_ok > 0 and n_ok >= 0.5 * max(n_any, 1):
                ch.numeric = True
                ch.y = np.asarray([np.nan if v is None else v for v in vals], dtype=float)
            else:
                ch.numeric = False
                ch.y = None
            from .model import normalize_name, normalize_unit

            key = (normalize_name(ch.name), normalize_unit(ch.unit))
            ch.occurrence = occurrences.get(key, 0)
            occurrences[key] = ch.occurrence + 1
        # usuń puste kolumny (bez nazwy i bez danych)
        grp.channels = [c for c in grp.channels if c.raw and any(r for r in c.raw)]

    return LogData(path=path, meta=meta, groups=groups, blocks=blocks)
