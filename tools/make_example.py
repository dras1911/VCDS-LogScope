"""Tworzy zanonimizowany przykładowy log do repozytorium (tests/data/przyklad.csv).

Z logu źródłowego usuwane są dane identyfikujące pojazd: numer VCID, dokładny numer
części sterownika, kod silnika, data i godzina sesji. Wartości pomiarowe zostają bez zmian,
żeby przykładowe zrzuty ekranu i testy były realistyczne.

Użycie:
    .venv/Scripts/python.exe tools/make_example.py [log_zrodlowy] [plik_wyjsciowy]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcds_viewer.parser import read_text  # noqa: E402

DEFAULT_SRC = ROOT / "LOG-01-031-002-011-V10.CSV"
DEFAULT_OUT = ROOT / "tests" / "data" / "przyklad.csv"


def anonymize(src: Path, out: Path) -> Path:
    lines = read_text(src).split("\n")

    # nagłówek: data/godzina + VCID + numer części sterownika
    lines[0] = re.sub(r"VCID:[0-9A-Fa-f\-]+", "VCID:0000000000000000-0000", lines[0])
    lines[0] = re.sub(r"^\w+,(\d+),(\w+),(\d+)", r"Wtorek,\1,\2,2026", lines[0])
    lines[0] = re.sub(r"\b\d{1,2}:\d{2}:\d{2}\b", "12:00:00", lines[0])
    if len(lines) > 1:
        fields = lines[1].split(",")
        if fields and fields[0].strip():
            fields[0] = "XXX 906 018 XX"
        if len(fields) > 2 and fields[2].strip():
            fields[2] = "1.8L R4/5VT         0001"
        lines[1] = ",".join(fields)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="cp1250")
    print(f"Zapisano przykładowy log: {out}")
    return out


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    if not src.exists():
        print(f"Brak pliku źródłowego: {src}")
        return 2
    anonymize(src, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
