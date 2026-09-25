"""Diagnostyka „ścian/igieł” przy osi obrotów.

Dla każdej serii odtwarza pipeline z `plot_xy` (przebiegi + sortowanie po obrotach)
i wypisuje pary sąsiednich (po X) próbek, które mają duży skok Y — z podziałem na:

  * ŚCIANA (dt > limit)  → połączenie próbek z odległych momentów; `_insert_gaps`
    powinien je rozciąć (jeśli na wykresie widać linię — rozcinanie nie działa),
  * igła (dt <= limit)   → prawdziwy skok w danych (np. obciążenie 154% → 10%
    przy odcięciu wtrysku) — program ma ją pokazywać wiernie, to nie błąd.

Użycie:
    .venv/Scripts/python.exe tools/check_walls.py [log.csv ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.model import LogData, X_RPM  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402


def analyse(path: Path) -> None:
    log = parse_log(str(path))
    print(f"\n=== {path.name} ===")
    print(f"przebiegi: {len(log.rpm_segments())}")
    rpm = log.rpm_series()
    if rpm is None:
        print("brak serii obrotów")
        return
    rt, _ = rpm
    for ch in log.channels:
        if not ch.has_data or ch.is_rpm:
            continue
        y = np.asarray(ch.y, dtype=float)
        finite = y[np.isfinite(y)]
        if len(finite) < 3:
            continue
        rng = float(finite.max() - finite.min())
        if rng <= 0:
            continue
        x = log.x_for(ch, X_RPM)
        ch_t = np.asarray(ch.t, dtype=float)
        limit = LogData._gap_limit(ch_t)
        n_wall, n_needle = 0, 0
        examples: list[str] = []
        for a, b in log.rpm_segments():
            t0 = float(rt[a])
            t1 = float(rt[min(b, len(rt) - 1)])
            mask = (ch_t >= t0) & (ch_t <= t1)
            if not mask.any():
                continue
            order = np.argsort(x[mask], kind="stable")
            xs = x[mask][order]
            ys = y[mask][order]
            ts = ch_t[mask][order]
            dx = np.abs(np.diff(ys))
            dt = np.abs(np.diff(ts))
            for i in np.where(dx > 0.5 * rng)[0]:
                if dt[i] > limit:
                    n_wall += 1
                    label = "ŚCIANA"
                else:
                    n_needle += 1
                    label = "igła  "
                if len(examples) < 5:
                    examples.append(
                        f"  {label} @ x={xs[i]:.0f}→{xs[i + 1]:.0f} "
                        f"y={ys[i]:.0f}→{ys[i + 1]:.0f} dt={dt[i]:.2f}s (limit {limit:.2f}s)"
                    )
        if n_wall or n_needle:
            print(f"  {ch.name} [{ch.unit}] range={rng:.0f}: "
                  f"ściany(do rozcięcia)={n_wall}, prawdziwe igły={n_needle}")
            for line in examples:
                print(line)


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or sorted(ROOT.glob("LOG-*.CSV"))
    if not paths:
        print("brak plików — podaj log CSV")
        return 1
    for p in paths:
        analyse(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
