"""Rzetelna kontrola: czy na wykresie przy osi obrotów zostają „ściany”.

Odtwarza tę samą ścieżkę co `plot_xy` (przebiegi → sortowanie po obrotach → rozcięcie
przerw), ale prowadzi też tablicę czasów próbek. Sprawdza potem pary, które w rysowanej
linii sąsiadują BEZ przerwy (NaN) — jeśli którąś dzieli przerwa czasowa większa niż próg,
to na wykresie jest pionowa „ściana”, której w danych nie było.

Wynik porównuje z faktycznym `plot_xy`, żeby mieć pewność, że kontrola dotyczy tego,
co naprawdę widać.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.model import LogData, X_RPM  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402


def cut_with_times(x: np.ndarray, y: np.ndarray, t: np.ndarray, limit: float):
    """To samo co LogData._insert_gaps, ale rozcina również tablicę czasów."""
    if len(x) < 2:
        return x, y, t
    jumps = np.where(np.abs(np.diff(t)) > limit)[0]
    if not len(jumps):
        return x, y, t
    ox, oy, ot = [], [], []
    start = 0
    for i in jumps:
        ox.append(x[start:i + 1])
        oy.append(y[start:i + 1])
        ot.append(t[start:i + 1])
        for bucket in (ox, oy, ot):
            bucket.append(np.array([np.nan]))
        start = i + 1
    ox.append(x[start:])
    oy.append(y[start:])
    ot.append(t[start:])
    return np.concatenate(ox), np.concatenate(oy), np.concatenate(ot)


def reconstruct(log: LogData, ch):
    """(x, y, t) dokładnie w kolejności rysowania."""
    x = np.asarray(log.x_for(ch, X_RPM), dtype=float)
    y = np.asarray(ch.y, dtype=float)
    ch_t = np.asarray(ch.t, dtype=float)
    rpm = log.rpm_series()
    rt = rpm[0] if rpm else None
    limit = LogData._gap_limit(ch_t)
    out_x, out_y, out_t = [], [], []
    covered = np.zeros(len(x), dtype=bool)
    for a, b in log.rpm_segments():
        t0 = float(rt[a])
        t1 = float(rt[min(b, len(rt) - 1)])
        mask = (ch_t >= t0) & (ch_t <= t1)
        if not mask.any():
            continue
        covered |= mask
        order = np.argsort(x[mask], kind="stable")
        sx, sy, st = cut_with_times(x[mask][order], y[mask][order], ch_t[mask][order], limit)
        out_x.append(sx)
        out_y.append(sy)
        out_t.append(st)
        for bucket in (out_x, out_y, out_t):
            bucket.append(np.array([np.nan]))
    if not covered.all():
        mask = ~covered
        order = np.argsort(x[mask], kind="stable")
        sx, sy, st = cut_with_times(x[mask][order], y[mask][order], ch_t[mask][order], limit)
        out_x.append(sx)
        out_y.append(sy)
        out_t.append(st)
    return np.concatenate(out_x), np.concatenate(out_y), np.concatenate(out_t)


def check(path: Path) -> int:
    log = parse_log(str(path))
    print(f"\n=== {path.name} ===")
    bad = 0
    for ch in log.channels:
        if not ch.has_data or ch.is_rpm:
            continue
        limit = LogData._gap_limit(np.asarray(ch.t, dtype=float))
        px, py = log.plot_xy(ch, X_RPM, split_sweeps=True)
        rx, ry, rt = reconstruct(log, ch)
        if not (len(px) == len(rx) and np.allclose(np.nan_to_num(px, nan=-1e9),
                                                  np.nan_to_num(rx, nan=-1e9))
                and np.allclose(np.nan_to_num(py, nan=-1e9), np.nan_to_num(ry, nan=-1e9))):
            print(f"  {ch.name}: UWAGA — kontrola nie odtwarza rysowania")
            bad += 1
            continue
        # pary sąsiadujące w linii (obie skończone = brak przerwy między nimi)
        both = np.isfinite(rt[:-1]) & np.isfinite(rt[1:])
        dt = np.abs(np.diff(rt))[both]
        walls = int((dt > limit).sum())
        if walls:
            bad += walls
            print(f"  ŚCIANA: {ch.name} [{ch.unit}] — {walls} par bez przerwy, "
                  f"największa przerwa {dt.max():.2f}s (limit {limit:.2f}s)")
    print("  problemow w tym logu:", bad)
    return bad


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or sorted(ROOT.glob("LOG-*.CSV"))
    total = sum(check(p) for p in paths)
    print("\nWNIOSEK:", "linie rozciete poprawnie — pionowe kreski to prawdziwe skoki danych"
          if total == 0 else f"znaleziono {total} nierozcietych par")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
