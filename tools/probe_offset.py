"""Prototyp: automatyczne dopasowanie dwóch logów w czasie (korelacja krzyżowa)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.parser import parse_log          # noqa: E402
from vcds_viewer.compare import interp_series  # noqa: E402

a = parse_log(ROOT / "LOG-01-031-002-011-V10.CSV")
b = parse_log(ROOT / "LOG-01-020-115-118-V10.CSV")
print("log A:", a.meta.file_name, "log B:", b.meta.file_name)

keys = [k for k in a.match_index() if k in set(b.match_index())]
print("wspolne parametry:", len(keys))


def grid_of(log, step=0.1):
    t = np.concatenate([g.t for g in log.groups if len(g.t)])
    return float(np.min(t)), float(np.max(t)), step


def score(shift, keys, t0, t1, step):
    """Suma korelacji (Pearsona) wspólnych kanałów przy danym przesunięciu logu B."""
    grid = np.arange(t0, t1 + step, step)
    total, used = 0.0, 0
    for k in keys:
        ca, cb = a.find(k), b.find(k)
        if ca is None or cb is None or not ca.has_data or not cb.has_data:
            continue
        ya = interp_series(np.asarray(ca.t, float), np.asarray(ca.y, float), grid)
        yb = interp_series(np.asarray(cb.t, float) + shift, np.asarray(cb.y, float), grid)
        m = np.isfinite(ya) & np.isfinite(yb)
        if m.sum() < 20:
            continue
        x, y = ya[m], yb[m]
        if np.std(x) < 1e-9 or np.std(y) < 1e-9:
            continue
        total += float(np.corrcoef(x, y)[0, 1])
        used += 1
    return (total / used if used else -2.0), used


t0a, t1a, _ = grid_of(a)
t0b, t1b, _ = grid_of(b)
print("zakres A: %.2f..%.2f s   zakres B: %.2f..%.2f s" % (t0a, t1a, t0b, t1b))

best = None
for shift in np.arange(-10.0, 10.001, 0.1):
    s, used = score(round(shift, 2), keys, max(t0a, t0b + shift), min(t1a, t1b + shift), 0.1)
    if best is None or s > best[0]:
        best = (s, round(shift, 2), used)
print("najlepsze przesuniecie: %.2f s  (korelacja %.3f, kanalow %d)" % (best[1], best[0], best[2]))

# wykres korelacji wokół optimum
print("\nprofil korelacji:")
for shift in np.arange(best[1] - 1.0, best[1] + 1.01, 0.2):
    s, used = score(round(shift, 2), keys, max(t0a, t0b + shift), min(t1a, t1b + shift), 0.1)
    bar = "#" * int(max(0, (s + 1)) * 20)
    print("  %+5.2f s  %+.3f  %s" % (shift, s, bar))

print("\ndla porownania, korelacja przy zerze:", "%.3f" % score(0.0, keys, max(t0a, t0b), min(t1a, t1b), 0.1)[0])
