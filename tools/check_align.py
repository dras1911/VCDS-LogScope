"""Sprawdzenie, jak program dopasuje dwa logi w czasie (diagnostyka zgłoszeń).

Użycie:
    .venv/Scripts/python.exe tools/check_align.py logA.csv logB.csv

Wypisuje wykryte przesunięcie, zgodność i profil korelacji — przydaje się, gdy użytkownik
mówi „logi nie chcą się dopasować”.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.model import _channel_xy, _detrend_zscore, best_time_offset  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402


def profile(ref, other, limit: float = 6.0, step: float = 0.2):
    """Profil zgodności w funkcji przesunięcia (do oceny, czy szczyt jest wyraźny)."""
    pairs = []
    for key in ref.common_keys(other):
        ca, cb = ref.find(key), other.find(key)
        if ca is None or cb is None or not ca.has_data or not cb.has_data:
            continue
        pa, pb = _channel_xy(ca), _channel_xy(cb)
        if pa and pb:
            pairs.append((pa, pb))
    if not pairs:
        return []
    t0r = min(p[0][0][0] for p in pairs)
    t1r = max(p[0][0][-1] for p in pairs)
    t0o = min(p[1][0][0] for p in pairs)
    t1o = max(p[1][0][-1] for p in pairs)
    w0, w1 = max(t0r, t0o + limit), min(t1r, t1o - limit)
    if w1 - w0 < 2.0:
        return []
    grid = np.arange(w0, w1 + step, step)
    win = max(3, int(2.0 / step))
    refs = [_detrend_zscore(np.interp(grid, ta, ya, left=np.nan, right=np.nan), win)
            for (ta, ya), _ in pairs]
    out = []
    for off in np.arange(-limit, limit + step / 2, step):
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
        out.append((round(float(off), 2), float(np.mean(scores)) if scores else -2.0))
    return out


def main() -> int:
    args = [a for a in sys.argv[1:] if a.lower().endswith((".csv", ".txt"))]
    if len(args) < 2:
        print(__doc__)
        return 2
    a, b = (parse_log(p) for p in args[:2])
    print(f"A: {a.meta.file_name}  ({len(a.channels)} kanałów)")
    print(f"B: {b.meta.file_name}  ({len(b.channels)} kanałów)")
    print(f"wspólne parametry: {len(a.common_keys(b))}")
    res = best_time_offset(a, b)
    if res is None:
        print("WYNIK: brak wspólnych parametrów z danymi — nie ma czego dopasować")
        return 1
    off, score, contrast, used = res
    print(f"WYNIK: przesunięcie logu B = {off:+.2f} s   zgodność = {score:.3f}   "
          f"kontrast = {contrast:.3f}   użyte kanały = {used}")
    if contrast < 0.05:
        print("UWAGA: szczyt jest płaski — logi prawdopodobnie pochodzą z różnych przejazdów")
    prof = profile(a, b)
    if prof:
        best = max(prof, key=lambda p: p[1])
        print(f"\nprofil (szczyt przy {best[0]:+.2f} s):")
        for s, v in prof:
            if abs(s - best[0]) <= 1.5:
                print(f"  {s:+6.2f} s  {v:+.3f}  {'#' * int(max(0.0, v + 1) * 24)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
