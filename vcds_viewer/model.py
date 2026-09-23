"""Model danych logu VCDS: kanały (serie), grupy pomiarowe i cały log."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

# Nazwy kanałów, które traktujemy jako obroty silnika (oś X w trybie RPM).
RPM_PATTERNS = ("obroty", "engine speed", "drehzahl", "rpm")

# Tryby osi X wykresu.
X_TIME = "time"
X_RPM = "rpm"


def normalize_name(name: str) -> str:
    """Klucz porównawczy nazwy parametru (bez wielkości liter i zbędnych spacji)."""
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def normalize_unit(unit: str) -> str:
    """Klucz porównawczy jednostki (bez spacji i wielkości liter)."""
    return (unit or "").strip().lower().replace(" ", "")


def clean_unit(unit: str) -> str:
    """Zamienia zapis VCDS (np. '*C', ' *PGMP') na czytelny (°C, °PGMP)."""
    u = (unit or "").strip()
    if u.startswith("*"):
        u = "°" + u[1:]
    return u


@dataclass
class LogMeta:
    """Nagłówek logu: data, wersja VCDS, dane sterownika."""

    weekday: str = ""
    date: str = ""
    time: str = ""
    vcds_version: str = ""
    data_version: str = ""
    ecu: str = ""
    engine: str = ""
    vcid: str = ""
    source: str = ""

    @property
    def file_name(self) -> str:
        return Path(self.source).name if self.source else ""

    def summary(self) -> str:
        parts = []
        if self.date:
            parts.append(f"{self.weekday.lower()}, {self.date}" if self.weekday else self.date)
        if self.time:
            parts.append(f"godz. {self.time}")
        if self.ecu:
            parts.append(self.ecu)
        if self.engine:
            parts.append(self.engine.strip())
        return "  •  ".join(parts)

    def detail(self) -> str:
        parts = []
        if self.vcds_version:
            parts.append(f"VCDS {self.vcds_version}")
        if self.data_version:
            parts.append(f"dane {self.data_version}")
        if self.vcid:
            parts.append(f"VCID {self.vcid}")
        return "  •  ".join(parts)


@dataclass
class Channel:
    """Pojedyncza seria pomiarowa (jedna kolumna jednej grupy)."""

    name: str
    unit: str
    group: str
    group_id: str
    t: np.ndarray                      # czasy próbek [s] (kolumna CZAS danej grupy)
    y: Optional[np.ndarray]            # wartości liczbowe (None dla kolumn binarnych/tekstowych)
    raw: list = field(default_factory=list)   # surowe wartości tekstowe
    numeric: bool = True
    occurrence: int = 0                # który to raz ta sama nazwa+jednostka w logu
    dup_index: int = 0                 # numer powtórzenia nazwy w obrębie grupy (0-based)
    dup_count: int = 1                 # ile razy ta nazwa występuje w grupie

    @property
    def match_key(self) -> tuple:
        """Klucz dopasowania tego samego parametru między logami."""
        return (normalize_name(self.name), normalize_unit(self.unit), self.occurrence)

    @property
    def display_name(self) -> str:
        """Nazwa do wyświetlenia — powtórzone parametry dostają numer (#1, #2…)."""
        if self.dup_count > 1:
            return f"{self.name} #{self.dup_index + 1}"
        return self.name

    @property
    def unit_label(self) -> str:
        return f"[{self.unit}]" if self.unit else ""

    @property
    def label(self) -> str:
        return f"{self.display_name} (grupa {self.group}) {self.unit_label}".strip()

    @property
    def short_label(self) -> str:
        return f"{self.display_name} {self.unit_label}".strip()

    @property
    def is_rpm(self) -> bool:
        n = normalize_name(self.name)
        return any(p in n for p in RPM_PATTERNS)

    @property
    def has_data(self) -> bool:
        return self.y is not None and len(self.y) > 0

    def stats(self) -> tuple[float, float, float]:
        """(min, max, średnia) dla serii liczbowej."""
        if not self.has_data:
            return (float("nan"),) * 3
        return float(np.nanmin(self.y)), float(np.nanmax(self.y)), float(np.nanmean(self.y))

    def value_at(self, x: float) -> Optional[float]:
        """Wartość najbliższej próbki dla podanego x (czas lub RPM)."""
        if not self.has_data or len(self.t) == 0:
            return None
        i = int(np.searchsorted(self.t, x))
        i = min(max(i, 0), len(self.t) - 1)
        if i > 0 and abs(self.t[i - 1] - x) <= abs(self.t[i] - x):
            i -= 1
        return float(self.y[i])


@dataclass
class Group:
    """Grupa pomiarowa VCDS (np. Grupa A: 031)."""

    letter: str
    group_id: str
    time_label: str = "CZAS"
    channels: list[Channel] = field(default_factory=list)
    t: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def title(self) -> str:
        return f"Grupa {self.letter}: {self.group_id}".strip(": ")

    @property
    def n_samples(self) -> int:
        return len(self.t)


@dataclass
class LogData:
    """Cały wczytany log VCDS."""

    path: str
    meta: LogMeta
    groups: list[Group] = field(default_factory=list)
    blocks: int = 1

    # ------------------------------------------------------------------ kanały
    @property
    def channels(self) -> list[Channel]:
        out: list[Channel] = []
        for g in self.groups:
            out.extend(g.channels)
        return out

    @property
    def numeric_channels(self) -> list[Channel]:
        return [c for c in self.channels if c.has_data]

    @property
    def text_channels(self) -> list[Channel]:
        return [c for c in self.channels if c.numeric and not c.has_data]

    def find(self, match_key: tuple) -> Optional[Channel]:
        for c in self.channels:
            if c.match_key == match_key:
                return c
        return None

    # ------------------------------------------------------------------- czas
    @property
    def t_start(self) -> float:
        ts = [g.t[0] for g in self.groups if len(g.t)]
        return float(min(ts)) if ts else 0.0

    @property
    def t_end(self) -> float:
        ts = [g.t[-1] for g in self.groups if len(g.t)]
        return float(max(ts)) if ts else 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.t_end - self.t_start)

    @property
    def n_rows(self) -> int:
        return max((g.n_samples for g in self.groups), default=0)

    # ---------------------------------------------------------------- obroty
    def rpm_series(self) -> Optional[tuple[np.ndarray, np.ndarray]]:
        """Połączona seria obrotów z całego logu (do osi X w trybie RPM)."""
        ts, ys = [], []
        for c in self.channels:
            if c.is_rpm and c.has_data:
                ts.append(np.asarray(c.t, dtype=float))
                ys.append(np.asarray(c.y, dtype=float))
        if not ts:
            return None
        t = np.concatenate(ts)
        y = np.concatenate(ys)
        order = np.argsort(t, kind="stable")
        t, y = t[order], y[order]
        # uśrednij duplikaty czasowe, by np.interp dostał rosnący, jednoznaczny x
        uniq, idx = np.unique(t, return_inverse=True)
        if len(uniq) != len(t):
            sums = np.zeros(len(uniq))
            counts = np.zeros(len(uniq))
            np.add.at(sums, idx, y)
            np.add.at(counts, idx, 1.0)
            y = sums / np.maximum(counts, 1.0)
            t = uniq
        return t, y

    def x_for(self, channel: Channel, mode: str = X_TIME) -> np.ndarray:
        """Zwraca wartości osi X dla danego kanału (czas albo RPM)."""
        if mode == X_TIME:
            return np.asarray(channel.t, dtype=float)
        rpm = self.rpm_series()
        if rpm is None:
            return np.asarray(channel.t, dtype=float)
        rt, ry = rpm
        return np.interp(np.asarray(channel.t, dtype=float), rt, ry)

    def rpm_at(self, t: float) -> Optional[float]:
        """Obroty interpolowane w czasie t (do mapowania osi RPM ↔ czas)."""
        rpm = self.rpm_series()
        if rpm is None:
            return None
        rt, ry = rpm
        return float(np.interp(t, rt, ry))

    def rpm_nearest(self, t: float) -> Optional[float]:
        """Obroty z najbliższej próbki — ta sama wartość, którą pokazuje dymek przy kursorze."""
        rpm = self.rpm_series()
        if rpm is None:
            return None
        rt, ry = rpm
        i = int(np.searchsorted(rt, t))
        i = min(max(i, 0), len(rt) - 1)
        if i > 0 and abs(rt[i - 1] - t) <= abs(rt[i] - t):
            i -= 1
        return float(ry[i])

    # -------------------------------------------------------------- dopasowanie
    def match_index(self) -> dict[tuple, Channel]:
        return {c.match_key: c for c in self.numeric_channels}

    def common_keys(self, other: "LogData") -> list[tuple]:
        """Klucze parametrów wspólnych dla dwóch logów (w kolejności tego logu)."""
        mine = self.match_index()
        theirs = other.match_index()
        return [k for k in mine if k in theirs]
