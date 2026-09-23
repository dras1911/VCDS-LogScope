"""Tworzy wydanie na GitHubie i wgrywa plik .exe jako załącznik.

Wykorzystuje poświadczenia zapisane przez Git Credential Manager (nie wypisuje ich nigdzie).

Użycie:
    .venv/Scripts/python.exe tools/create_release.py [--tag v1.0] [--exe ścieżka] [--dry-run]
"""

from __future__ import annotations

import json
import mimetypes
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "dras1911/VCDS-LogScope"
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"

NOTES = """## VCDS LogScope 1.0

Czytelna wizualizacja logów z **VCDS / VAG-COM** — program dla Windows (Python + PySide6 + pyqtgraph).

### Co potrafi

**Wykres nakładany (styl TuneZilla)**
- wszystkie parametry na jednym wykresie, każdy w swoim kolorze dobranym wg rodzaju parametru
- linia pomocnicza (kursor) z kropkami na każdej serii i dymkiem wartości
- **etykieta przy osi X pokazująca jednocześnie czas i obroty** w miejscu kursora (w TuneZilli trzeba się domyślać)
- oś X: **czas [s]** albo **obroty [obr/min]**; normalizacja 0–100% dla parametrów o różnych zakresach
- zoom rolką (oś X), `Ctrl`+rolka (oś Y), przeciąganie, dwuklik = dopasowanie

**Tabela z kolorowaniem narastającym**
- kolumny w blokach „Grupa A/B/C” z dwupoziomowym nagłówkiem
- heatmapa (zielona skala jak w TuneZilli, do wyboru też inne)
- strzałki wzrostów/spadków ▲▼ względem poprzedniego wiersza
- wiersz podąża za kursorem wykresu, klik w wiersz ustawia kursor

**Porównanie dwóch lub więcej logów**
- nakładka: log A linią ciągłą, log B przerywaną, C kropkowaną…
- tabela różnic Δ = log B − log A na wspólnej siatce czasu z kolorowaniem delt
- statystyki (min/max/średnia, średnia i maksymalna różnica) oraz przesunięcie czasowe logu B

**Obsługa logów VCDS**
- eksport CSV w wersji polskiej, angielskiej i niemieckiej (kodowanie CP1250/CP1252/UTF-8)
- 1–3 grupy pomiarowe, osobne kolumny czasu każdej grupy, kolumny binarne, wiele bloków w pliku
- automatyczne rozpoznawanie parametrów i jednostek (`/min`, `%`, `ms`, `g/s`, `°C`, `°PGMP`, `mbar`…)

### Pliki do pobrania

- **`VCDS LogScope.exe`** — wersja jednoplikowa (zalecana), nie wymaga instalacji ani Pythona
- `VCDS-LogScope-1.0-portable.zip` — wersja katalogowa (szybszy start, bez rozpakowywania do TEMP)

Wymagania: Windows 10/11 64-bit. Program jest przenośny — nic nie instaluje w systemie.

### Szybki start

1. Uruchom `VCDS LogScope.exe`
2. `Ctrl+O` albo przeciągnij plik CSV z VCDS na okno programu
3. Najedź myszą na wykres — linia kursora pokaże wartości wszystkich parametrów
4. `Ctrl+T` — porównanie dwóch logów

Pełny opis: [README](https://github.com/dras1911/VCDS-LogScope#readme)
"""


def get_token() -> str:
    """Pobiera token GitHub z menedżera poświadczeń git (wartość nie jest nigdzie wypisywana)."""
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, check=True,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("Brak poświadczeń GitHub w menedżerze (git credential fill nic nie zwrócił).")


def api(token: str, method: str, url: str, payload=None, content_type="application/json"):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode() if content_type == "application/json" else payload
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "VCDS-LogScope-release")
    if data is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body.strip().startswith(("{", "[")) else {}
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:400]}")
        raise


def upload_asset(token: str, release_id: int, path: Path) -> str:
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    url = f"{UPLOADS}/repos/{REPO}/releases/{release_id}/assets?name={urllib.parse.quote(path.name)}"
    print(f"Wgrywam {path.name} ({path.stat().st_size / 1e6:.1f} MB)…")
    res = api(token, "POST", url, payload=path.read_bytes(), content_type=ctype)
    return res.get("browser_download_url", "")


def main() -> int:
    args = sys.argv[1:]
    tag = "v1.0"
    if "--tag" in args:
        tag = args[args.index("--tag") + 1]
    exe = ROOT / "dist" / "onefile" / "VCDS LogScope.exe"
    if "--exe" in args:
        exe = Path(args[args.index("--exe") + 1])
    zip_path = ROOT / "dist" / f"VCDS-LogScope-1.0-portable.zip"

    token = get_token()
    user = api(token, "GET", f"{API}/user")
    print(f"Zalogowany jako: {user.get('login')}")

    existing = None
    try:
        existing = api(token, "GET", f"{API}/repos/{REPO}/releases/tags/{tag}")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    if existing:
        print(f"Wydanie {tag} już istnieje: {existing.get('html_url')}")
        release = existing
    else:
        release = api(token, "POST", f"{API}/repos/{REPO}/releases", payload={
            "tag_name": tag,
            "name": f"VCDS LogScope {tag.lstrip('v')}",
            "body": NOTES,
            "draft": False,
            "prerelease": False,
        })
        print(f"Utworzono wydanie: {release.get('html_url')}")

    uploaded = []
    for asset in (exe, zip_path):
        if asset.exists():
            uploaded.append(upload_asset(token, release["id"], asset))
        else:
            print(f"(pomijam brakujący plik: {asset})")

    print("\nZałączniki:")
    for url in uploaded:
        print(" ", url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
