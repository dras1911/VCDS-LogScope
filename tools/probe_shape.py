"""Podglad tekstowy: obroty obu logow obok siebie (do oceny przesuniecia)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vcds_viewer.parser import parse_log               # noqa: E402

a = parse_log(ROOT / "LOG-01-031-002-011-V10.CSV")
b = parse_log(ROOT / "LOG-01-020-115-118-V10.CSV")


def series(log):
    for ch in log.channels:
        if ch.is_rpm and ch.has_data:
            t = np.asarray(ch.t, float)
            y = np.asarray(ch.y, float)
            m = np.isfinite(t) & np.isfinite(y)
            return t[m], y[m]
    return np.array([]), np.array([])


ta, ya = series(a)
tb, yb = series(b)
grid = np.arange(0, 96, 1.0)
ga = np.interp(grid, ta, ya, left=np.nan, right=np.nan)
gb = np.interp(grid, tb, yb, left=np.nan, right=np.nan)

print("  t[s] | A obroty (0..6200)          | B obroty (0..6200)")
for i, t in enumerate(grid):
    ba = int(round((ga[i] - 1000) / 5200 * 30)) if np.isfinite(ga[i]) else -1
    bb = int(round((gb[i] - 1000) / 5200 * 30)) if np.isfinite(gb[i]) else -1
    sa = ("%5.0f " % ga[i]) + ("#" * max(0, ba)).ljust(30) if ba >= 0 else "   .  " + " " * 30
    sb = ("%5.0f " % gb[i]) + ("#" * max(0, bb)).ljust(30) if bb >= 0 else "   .  " + " " * 30
    print("%5.0f | %s | %s" % (t, sa, sb))
