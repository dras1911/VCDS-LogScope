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
    # wyliczane przy pierwszym użyciu (patrz `steep_jumps`)
    _steep_jumps: Optional[int] = field(default=None, repr=False, compare=False)

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

    def rpm_segments(self, min_reversal: float = 60.0) -> list[tuple[int, int]]:
        """Przedziały serii obrotów o stałym kierunku (kolejne „przebiegi”).

        Gdy obroty rosną i maleją na zmianę (jazda na biegu jałowym, kilka przyrostów),
        rysowanie w funkcji obrotów w kolejności czasu tworzy pętle — ta sama wartość
        obrotów wypada w kilku momentach z różnymi wartościami pozostałych parametrów.
        Dzieląc dane w miejscach zawrotu obrotów i sortując każdy fragment po obrotach,
        dostajemy czytelne przebiegi bez pętli.
        """
        rpm = self.rpm_series()
        if rpm is None:
            return []
        _rt, ry = rpm
        n = len(ry)
        if n < 3:
            return [(0, n)]
        bounds = [0]
        direction = 0
        extreme = float(ry[0])
        for i in range(1, n):
            v = float(ry[i])
            if direction >= 0 and v >= extreme:
                extreme, direction = v, 1
            elif direction <= 0 and v <= extreme:
                extreme, direction = v, -1
            elif direction == 1 and extreme - v > min_reversal:
                bounds.append(i)
                extreme, direction = v, -1
            elif direction == -1 and v - extreme > min_reversal:
                bounds.append(i)
                extreme, direction = v, 1
        bounds.append(n)
        return [(bounds[k], bounds[k + 1]) for k in range(len(bounds) - 1)]

    def plot_xy(self, channel: Channel, mode: str = X_TIME,
                split_sweeps: bool = False) -> tuple[np.ndarray, np.ndarray]:
        """Zwraca (x, y) gotowe do narysowania.

        W trybie RPM z `split_sweeps=True` linia jest dzielona na przebiegi (przerwy = NaN),
        a każdy przebieg sortowany po obrotach — dzięki temu nie ma pętli.
        """
        y = np.asarray(channel.y, dtype=float)
        if mode == X_TIME:
            return np.asarray(channel.t, dtype=float), y
        x = self.x_for(channel, X_RPM)
        if not split_sweeps:
            return x, y
        rpm = self.rpm_series()
        if rpm is None or len(x) < 3:
            return x, y
        rt, _ry = rpm
        segments = self.rpm_segments()
        if len(segments) <= 1:
            order = np.argsort(x, kind="stable")
            return x[order], y[order]
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        covered = np.zeros(len(x), dtype=bool)
        ch_t = np.asarray(channel.t, dtype=float)
        limit = self._gap_limit(ch_t)
        for a, b in segments:
            t0 = float(rt[a])
            t1 = float(rt[min(b, len(rt) - 1)])
            mask = (ch_t >= t0) & (ch_t <= t1)
            if not mask.any():
                continue
            covered |= mask
            order = np.argsort(x[mask], kind="stable")
            seg_x, seg_y = self._insert_gaps(x[mask][order], y[mask][order],
                                             ch_t[mask][order], limit)
            xs.append(seg_x)
            ys.append(seg_y)
            xs.append(np.array([np.nan]))
            ys.append(np.array([np.nan]))
        if not covered.all():     # próbki poza zakresem obrotów — osobny fragment
            mask = ~covered
            order = np.argsort(x[mask], kind="stable")
            seg_x, seg_y = self._insert_gaps(x[mask][order], y[mask][order],
                                             ch_t[mask][order], limit)
            xs.append(seg_x)
            ys.append(seg_y)
        if not xs:
            return x, y
        return np.concatenate(xs), np.concatenate(ys)

    @staticmethod
    def mean_by_rpm(x: np.ndarray, y: np.ndarray, bins: int = 120,
                    smooth: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Średnia wartość w przedziałach obrotów — czytelna charakterystyka.

        Przy osi obrotów ten sam parametr ma przy tych samych obrotach różne wartości
        (kąt zapłonu zależy też od obciążenia), więc linia łącząca surowe próbki tworzy
        zygzaki. Uśrednienie w przedziałach pokazuje trend: „ile wynosi ten parametr
        przy danych obrotach”. Przedziały bez próbek zostają puste (przerwa w linii),
        a sąsiednie średnie są dodatkowo lekko wygładzane, żeby charakterystyka była gładka.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        mask = np.isfinite(x) & np.isfinite(y)
        xs, ys = x[mask], y[mask]
        if len(xs) < 3:
            return xs, ys
        lo, hi = float(xs.min()), float(xs.max())
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            return xs, ys
        # Liczba przedziałów musi być DUŻO mniejsza niż liczba próbek — inaczej w każdym
        # przedziale jest 0–1 próbek, powstają dziury i „średnia” wygląda jak surowe dane.
        # Cel: kilka próbek na przedział (im więcej, tym gładsza charakterystyka).
        bins = max(6, min(int(bins), len(xs) // 5))
        edges = np.linspace(lo, hi, bins + 1)
        idx = np.clip(np.digitize(xs, edges) - 1, 0, bins - 1)
        sums = np.bincount(idx, weights=ys, minlength=bins)
        counts = np.bincount(idx, minlength=bins)
        centers = (edges[:-1] + edges[1:]) / 2.0
        mean = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
        if smooth:
            mean = LogData._smooth3(mean)
        return centers, mean

    @staticmethod
    def _smooth3(values: np.ndarray) -> np.ndarray:
        """Lekkie wygładzenie (średnia ruchoma z 3 przedziałów), puste przedziały zostają puste."""
        n = len(values)
        if n < 3:
            return values
        out = values.copy()
        for i in range(1, n - 1):
            window = values[i - 1:i + 2]
            window = window[np.isfinite(window)]
            if np.isfinite(values[i]) and len(window):
                out[i] = float(window.mean())
        return out

    @staticmethod
    def _gap_limit(t: np.ndarray) -> float:
        """Próg przerwy czasowej: powyżej niego łączymy próbki z odległych momentów."""
        if len(t) < 3:
            return 2.0
        dt = np.diff(np.sort(t))
        dt = dt[dt > 0]
        step = float(np.median(dt)) if len(dt) else 0.9
        return max(3.0 * step, 1.5)

    def steep_jumps(self, share: float = 0.35) -> int:
        """Ile razy wartość skoczyła o więcej niż `share` swojego zakresu w jednym kroku czasu.

        Takie skoki rysują się przy osi obrotów jako pionowe kreski — to prawdziwe dane
        (np. odcięcie wtrysku: obciążenie 120% → 14%), a nie sklejone przebiegi. Program
        rozcina wyłącznie pary próbek z odległych momentów (`_insert_gaps`), więc jeśli
        skok mieści się w jednym kroku czasu, jest pokazywany wiernie.
        """
        if self._steep_jumps is not None:
            return self._steep_jumps
        total = 0
        for ch in self.channels:
            if not ch.has_data or ch.is_rpm:
                continue
            raw_t = np.asarray(ch.t, dtype=float)
            y = np.asarray(ch.y, dtype=float)
            ok = np.isfinite(raw_t) & np.isfinite(y)
            t, y = raw_t[ok], y[ok]
            if len(y) < 3:
                continue
            span = float(np.nanmax(y) - np.nanmin(y))
            if span <= 0:
                continue
            limit = self._gap_limit(raw_t)
            jump = np.abs(np.diff(y)) > share * span
            within_step = np.abs(np.diff(t)) <= limit
            total += int(np.sum(jump & within_step))
        self._steep_jumps = total
        return total

    def stats_in_range(self, ch: Channel, mode: str, x0: float, x1: float
                       ) -> tuple[int, float, float, float]:
        """(liczba próbek, min, max, średnia) dla zaznaczonego zakresu osi X.

        Zakres liczymy w jednostkach osi, czyli dokładnie w tym, co widać w zaznaczonym
        pasmie: przy osi czasu to sekundy, przy osi obrotów — obroty.
        """
        if not ch.has_data:
            return (0, float("nan"), float("nan"), float("nan"))
        x = np.asarray(self.x_for(ch, mode), dtype=float)
        y = np.asarray(ch.y, dtype=float)
        ok = np.isfinite(x) & np.isfinite(y) & (x >= x0) & (x <= x1)
        if not ok.any():
            return (0, float("nan"), float("nan"), float("nan"))
        vals = y[ok]
        return (int(ok.sum()), float(np.min(vals)), float(np.max(vals)), float(np.mean(vals)))

    @staticmethod
    def _insert_gaps(x: np.ndarray, y: np.ndarray, t: np.ndarray,
                     limit: float) -> tuple[np.ndarray, np.ndarray]:
        """Rozcina linię tam, gdzie sąsiednie (po obrotach) próbki dzieli duży skok czasu.

        Sortowanie po obrotach zestawia ze sobą próbki z różnych momentów logu (np. dwa
        biegi jałowe). Połączenie ich linią daje pionowe „ściany”, których w rzeczywistości
        nie było — przerwa w linii pokazuje to uczciwie.
        """
        if len(x) < 2:
            return x, y
        jumps = np.where(np.abs(np.diff(t)) > limit)[0]
        if not len(jumps):
            return x, y
        out_x: list[np.ndarray] = []
        out_y: list[np.ndarray] = []
        start = 0
        for i in jumps:
            out_x.append(x[start:i + 1])
            out_y.append(y[start:i + 1])
            out_x.append(np.array([np.nan]))
            out_y.append(np.array([np.nan]))
            start = i + 1
        out_x.append(x[start:])
        out_y.append(y[start:])
        return np.concatenate(out_x), np.concatenate(out_y)

    def time_for_rpm(self, rpm_value: float) -> Optional[float]:
        """Czas najbliższej próbki o podanych obrotach (do etykiety kursora w trybie RPM)."""
        rpm = self.rpm_series()
        if rpm is None:
            return None
        rt, ry = rpm
        i = int(np.argmin(np.abs(ry - rpm_value)))
        return float(rt[i])

    # -------------------------------------------------------------- dopasowanie
    def match_index(self) -> dict[tuple, Channel]:
        return {c.match_key: c for c in self.numeric_channels}

    def common_keys(self, other: "LogData") -> list[tuple]:
        """Klucze parametrów wspólnych dla dwóch logów (w kolejności tego logu)."""
        mine = self.match_index()
        theirs = other.match_index()
        return [k for k in mine if k in theirs]


# ---------------------------------------------------------------- dopasowanie w czasie
def _moving_average(y: np.ndarray, win: int) -> np.ndarray:
    """Średnia ruchoma z dopełnieniem brzegów (do usunięcia wolnego trendu)."""
    if win < 3:
        return y
    k = np.ones(win) / win
    pad = win // 2
    yp = np.pad(y, pad, mode="edge")
    return np.convolve(yp, k, mode="same")[pad:pad + len(y)]


def _detrend_zscore(y: np.ndarray, win: int) -> np.ndarray:
    """Usuwa wolny trend i normalizuje — dzięki temu korelacja patrzy na kształt, nie na poziom."""
    y = np.asarray(y, dtype=float)
    if win >= 3:
        y = y - _moving_average(y, win)
    finite = np.isfinite(y)
    if finite.sum() < 2:
        return y
    sd = float(np.std(y[finite]))
    if sd < 1e-12:
        return y * np.nan
    return (y - float(np.mean(y[finite]))) / sd


def _channel_xy(ch) -> Optional[tuple[np.ndarray, np.ndarray]]:
    t = np.asarray(ch.t, dtype=float)
    y = np.asarray(ch.y, dtype=float)
    m = np.isfinite(t) & np.isfinite(y)
    if m.sum() < 5:
        return None
    return t[m], y[m]


def best_time_offset(ref: "LogData", other: "LogData", keys=None, max_shift: float = 20.0,
                     coarse: float = 0.1, fine: float = 0.02
                     ) -> Optional[tuple[float, float, float, int]]:
    """Szuka przesunięcia w czasie, przy którym log `other` pokrywa się z `ref`.

    Porównuje wspólne parametry po kształcie (wolny trend jest usuwany — inaczej
    oba logi „zgadzają się” wszędzie, bo oba rosną i maleją razem). Szuka metodą
    korelacji krzyżowej: najpierw zgrubnie co `coarse` s, potem dokładnie co `fine` s.

    Zwraca `(przesunięcie, zgodność, kontrast, liczba_kanałów)` albo `None`, gdy nie ma
    czego dopasowywać. Przesunięcie dodaje się do czasów logu `other` — dodatnie odsuwa
    jego wykres w prawo (tak samo działa „Przesunięcie B” w oknie porównania).
    """
    pairs: list[tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]] = []
    if keys is None:
        keys = ref.common_keys(other)
    for key in keys:
        ca, cb = ref.find(key), other.find(key)
        if ca is None or cb is None or not ca.has_data or not cb.has_data:
            continue
        pa, pb = _channel_xy(ca), _channel_xy(cb)
        if pa is None or pb is None:
            continue
        pairs.append((pa, pb))
    if not pairs:
        return None
    if len(pairs) > 8:
        # do dopasowania wystarczy kilka najbardziej „żywych” parametrów,
        # a mniej kanałów = szybsze liczenie
        pairs.sort(key=lambda p: -float(np.std(p[0][1])))
        pairs = pairs[:8]

    t0r = min(p[0][0][0] for p in pairs)
    t1r = max(p[0][0][-1] for p in pairs)
    t0o = min(p[1][0][0] for p in pairs)
    t1o = max(p[1][0][-1] for p in pairs)
    span = min(t1r - t0r, t1o - t0o)
    limit = min(max_shift, max(0.0, span / 3.0))
    if limit < 0.2:
        return None
    # okno wspólne dla KAŻDEGO przesunięcia z zakresu — inaczej brzegi fałszują wynik
    w0 = max(t0r, t0o + limit)
    w1 = min(t1r, t1o - limit)
    if w1 - w0 < 2.0:
        return None

    def profile(step: float, offsets: np.ndarray) -> list[tuple[float, float]]:
        # bezpiecznik wydajności: przy długich logach przerzedzamy siatkę,
        # żeby dopasowanie nie zamrażało okna (wynik zmienia się wtedy o setne sekundy)
        if (w1 - w0) / step > 3000:
            step = (w1 - w0) / 3000
        grid = np.arange(w0, w1 + step, step)
        win = max(3, int(2.0 / step))
        refs = [_detrend_zscore(np.interp(grid, ta, ya, left=np.nan, right=np.nan), win)
                for (ta, ya), _ in pairs]
        out: list[tuple[float, float]] = []
        for off in offsets:
            scores = []
            for rv, ((_, _), (tb, yb)) in zip(refs, pairs):
                ov = _detrend_zscore(np.interp(grid - off, tb, yb, left=np.nan, right=np.nan), win)
                m = np.isfinite(rv) & np.isfinite(ov)
                if m.sum() < 20:
                    continue
                x, y = rv[m], ov[m]
                if np.std(x) < 1e-12 or np.std(y) < 1e-12:
                    continue
                scores.append(float(np.corrcoef(x, y)[0, 1]))
            out.append((float(off), float(np.mean(scores)) if scores else -2.0))
        return out

    coarse_offsets = np.arange(-limit, limit + coarse / 2, coarse)
    prof = profile(coarse, coarse_offsets)
    if not prof:
        return None
    best_off, _ = max(prof, key=lambda p: p[1])
    fine_offsets = np.arange(best_off - coarse, best_off + coarse + fine / 2, fine)
    fine_prof = profile(fine, fine_offsets)
    best_off, best_score = max(fine_prof, key=lambda p: p[1])
    values = np.array([v for _, v in prof], dtype=float)
    contrast = best_score - float(np.median(values))
    used = max(1, sum(1 for _ in pairs))
    return round(float(best_off), 2), float(best_score), float(contrast), used
