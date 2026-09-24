"""Prototyp 3: dopasowanie logów po szczytach obrotów (cechy), nie po trendzie."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.parser import parse_log               # noqa: E402

a = parse_log(ROOT / "LOG-01-031-002-011-V10.CSV")
b = parse_log(ROOT / "LOG-01-020-115-118-V10.CSV")


def rpm_of(log):
    for ch in log.channels:
        if ch.is_rpm and ch.has_data:
            t = np.asarray(ch.t, float)
            y = np.asarray(ch.y, float)
            m = np.isfinite(t) & np.isfinite(y)
            return t[m], y[m]
    return np.array([]), np.array([])


def peaks(t, y, min_height=None, min_dist=1.0):
    """Lokalne maksima obrotów powyżej progu, odległe o co najmniej min_dist sekund."""
    if len(y) < 5:
        return np.array([])
    hi = np.percentile(y, 80) if min_height is None else min_height
    idx = [i for i in range(1, len(y) - 1)
           if y[i] >= y[i - 1] and y[i] > y[i + 1] and y[i] >= hi]
    picked = []
    for i in idx:
        if picked and t[i] - t[picked[-1]] < min_dist:
            if y[i] > y[picked[-1]]:
                picked[-1] = i
            continue
        picked.append(i)
    return t[picked]


ta, ya = rpm_of(a)
tb, yb = rpm_of(b)
print("A: %d probek obrotow %.0f..%.0f   B: %d probek %.0f..%.0f" % (
    len(ya), ya.min(), ya.max(), len(yb), yb.min(), yb.max()))

pa = peaks(ta, ya)
pb = peaks(tb, yb)
print("\nszczyty obrotow A (%d):" % len(pa), np.round(pa, 2))
print("szczyty obrotow B (%d):" % len(pb), np.round(pb, 2))

# dla kazdego przesuniecia: ile szczytow A ma blisko siebie szczyt B
print("\ndopasowanie szczytow (tolerancja 1.0 s):")
best = None
for s in np.arange(-6.0, 6.001, 0.1):
    shifted = pb + s
    hits, errs = 0, []
    for x in pa:
        d = np.abs(shifted - x)
        if len(d) and d.min() <= 1.0:
            hits += 1
            errs.append(float(d.min()))
    score = hits - (np.mean(errs) if errs else 0)
    if best is None or score > best[0]:
        best = (score, round(float(s), 2), hits, float(np.mean(errs)) if errs else float("nan"))
print("najlepsze: %+.2f s  (trafien %d, sredni blad %.2f s)" % (best[1], best[2], best[3]))

# szczegoly najlepszego dopasowania
s = best[1]
print("\nszczegoly przy %+.2f s:" % s)
for x in pa:
    d = np.abs((pb + s) - x)
    if len(d) and d.min() <= 1.5:
        j = int(np.argmin(d))
        print("   A %6.2f s  <->  B %6.2f s (+%+.2f)   roznica %+.2f s" % (
            x, pb[j], s, (pb[j] + s) - x))
