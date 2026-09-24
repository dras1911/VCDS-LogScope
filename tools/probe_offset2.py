"""Prototyp 2: dopasowanie logów po odtrendowanym sygnale (stałe okno nakładania)."""
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.parser import parse_log               # noqa: E402
from vcds_viewer.compare import interp_series          # noqa: E402

STEP = 0.05
SMAX = 8.0

a = parse_log(ROOT / "LOG-01-031-002-011-V10.CSV")
b = parse_log(ROOT / "LOG-01-020-115-118-V10.CSV")
keys = [k for k in a.match_index() if k in set(b.match_index())]


def span(log):
    t = np.concatenate([g.t for g in log.groups if len(g.t)])
    return float(np.min(t)), float(np.max(t))


ta0, ta1 = span(a)
tb0, tb1 = span(b)
print("zakres A: %.2f..%.2f  B: %.2f..%.2f" % (ta0, ta1, tb0, tb1))

G0 = min(ta0, tb0) - SMAX          # początek siatki
G1 = max(ta1, tb1) + SMAX          # koniec siatki
grid = np.arange(G0, G1 + STEP, STEP)
N = len(grid)
print("siatka: %.2f..%.2f  (%d probek, krok %.2f s)" % (G0, G1, N, STEP))

# okno bazowe ważne dla każdego przesunięcia z zakresu -SMAX..SMAX
W0, W1 = max(ta0, tb0 + SMAX), min(ta1, tb1 - SMAX)
print("okno dopasowania: %.2f..%.2f s (%.1f s)" % (W0, W1, W1 - W0))
i0, i1 = int(round((W0 - G0) / STEP)), int(round((W1 - G0) / STEP))


def moving_average(y, win):
    if win < 3:
        return y
    k = np.ones(win) / win
    pad = win // 2
    yp = np.pad(y, pad, mode="edge")
    return np.convolve(yp, k, mode="same")[pad:pad + len(y)]


def channels(method):
    out = {}
    for k in keys:
        ca, cb = a.find(k), b.find(k)
        if ca is None or cb is None or not ca.has_data or not cb.has_data:
            continue
        ya = interp_series(np.asarray(ca.t, float), np.asarray(ca.y, float), grid)
        yb = interp_series(np.asarray(cb.t, float), np.asarray(cb.y, float), grid)
        fin = np.isfinite(ya) & np.isfinite(yb)
        if fin.sum() < 100:
            continue
        if method == "detrend":
            win = max(3, int(3.0 / STEP))
            ya = ya - moving_average(ya, win)
            yb = yb - moving_average(yb, win)
        elif method == "diff":
            ya, yb = np.gradient(ya), np.gradient(yb)
        ya = ya - np.nanmean(ya)
        yb = yb - np.nanmean(yb)
        fin = np.isfinite(ya) & np.isfinite(yb)   # po przekształceniu NaN rozszerza się na brzegi
        if fin.sum() < 100:
            continue
        lo_f = int(np.argmax(fin))
        hi_f = int(len(fin) - np.argmax(fin[::-1]))
        out[k] = (ya, yb, lo_f, hi_f)
    return out


def profile(method, shifts):
    data = channels(method)
    if os.environ.get("DEBUG"):
        print("  [debug] kanalow:", len(data), " i0,i1 =", i0, i1)
        for k, (ya, yb, lo_f, hi_f) in data.items():
            off = 0
            c0, c1 = max(i0, lo_f, lo_f - off), min(i1, hi_f, hi_f - off)
            x, y = ya[c0:c1], yb[c0 + off:c1 + off]
            print("  [debug] %-24s lo_f=%d hi_f=%d len=%d/%d nan=%d/%d" % (
                k[0], lo_f, hi_f, len(x), len(y),
                int((~np.isfinite(x)).sum()), int((~np.isfinite(y)).sum())))
    res = []
    for s in shifts:
        off = int(round(s / STEP))
        scores = []
        for ya, yb, lo_f, hi_f in data.values():
            c0 = max(i0, lo_f, lo_f - off)
            c1 = min(i1, hi_f, hi_f - off)
            if c1 - c0 < 50:
                continue
            x, y = ya[c0:c1], yb[c0 + off:c1 + off]
            sx, sy = np.std(x), np.std(y)
            if sx < 1e-12 or sy < 1e-12:
                continue
            cc = float(np.corrcoef(x, y)[0, 1])
            if os.environ.get("DEBUG") and abs(s) < 0.001:
                print("      [dbg] %-20s len=%d nan=%d/%d std=%.4g/%.4g corr=%s" % (k[0], len(x), int((~np.isfinite(x)).sum()), int((~np.isfinite(y)).sum()), sx, sy, cc))
            scores.append(cc)
        res.append((round(float(s), 2), float(np.mean(scores)) if scores else -2.0))
    return res


shifts = np.arange(-4.0, 4.001, 0.1)
for method in ("raw", "detrend", "diff"):
    prof = profile(method, shifts)
    best = max(prof, key=lambda p: p[1])
    top = sorted(prof, key=lambda p: -p[1])[:5]
    print("\n=== metoda: %-8s -> najlepsze %+.2f s (%.3f)" % (method, best[0], best[1]))
    print("    TOP5: " + ", ".join("%+.2f(%.3f)" % t for t in top))
    for s, v in prof:
        if True:
            print("      %+5.2f  %+.3f  %s" % (s, v, "#" * int(max(0.0, v + 1) * 22)))
