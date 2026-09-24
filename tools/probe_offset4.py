"""Sprawdzenie: czy best_time_offset znajduje znane przesuniecie."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vcds_viewer.parser import parse_log                # noqa: E402
from vcds_viewer.model import best_time_offset          # noqa: E402

SAMPLE = ROOT / "LOG-01-031-002-011-V10.CSV"


def shifted(log, dt):
    clone = parse_log(log.path)
    for g in clone.groups:
        g.t = [float(x) + dt for x in g.t]
    for c in clone.channels:
        c.t = [float(x) + dt for x in c.t]
    return clone


base = parse_log(SAMPLE)
print("kanaly:", len(base.channels))
for dt in (1.1, -1.1, 3.0, 0.0):
    other = shifted(base, dt)
    res = best_time_offset(base, other)
    if res is None:
        print("dt=%+5.2f -> brak wyniku" % dt)
        continue
    off, score, contrast, used = res
    print("dt=%+5.2f -> wykryte %+6.2f s (oczekiwane %+6.2f)  zgodnosc=%.3f kontrast=%.3f kanalow=%d"
          % (dt, off, -dt, score, contrast, used))

# dwa rozne logi z repozytorium (maja rozne przebiegi)
b2 = parse_log(ROOT / "LOG-01-020-115-118-V10.CSV")
res = best_time_offset(base, b2)
print("\nrozne logi:", None if res is None else
      ("%+.2f s  zgodnosc=%.3f kontrast=%.3f kanalow=%d" % res))
