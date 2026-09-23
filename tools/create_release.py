"""Tworzy wydanie na GitHubie (własny numer dla każdej wersji) i wgrywa pliki .exe.

Numer wersji bierze z `vcds_viewer/__init__.py` — każde wydanie dostaje tag `vX.Y.Z`
i nowy wpis na liście wydań. Ponowne uruchomienie dla tej samej wersji podmienia
załączniki (przydatne, gdy build trzeba powtórzyć).

Poświadczenia pobiera z menedżera poświadczeń git (wartości nie są nigdzie wypisywane).

Użycie:
    .venv/Scripts/python.exe tools/create_release.py                  # wersja z pakietu
    .venv/Scripts/python.exe tools/create_release.py --dry-run        # tylko pokaż, co zrobi
    .venv/Scripts/python.exe tools/create_release.py --no-tag-push    # nie wypychaj tagu
"""

from __future__ import annotations

import json
import mimetypes
import re
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

DESCRIPTION = """Czytelne przeglądanie logów z **VCDS / VAG-COM** — program dla Windows, nie wymaga instalacji
ani internetu. Logi nie są nigdzie wysyłane.

### Co potrafi

**Wykres ze wszystkimi parametrami naraz** — w dwóch widokach
- **Nakładany**: wszystkie linie na jednym wykresie — od razu widać, jak parametry zachowują się względem siebie
- **Pasma**: każdy parametr w osobnym pasie z własną skalą — czytelny przy dowolnej liczbie parametrów
- linia kursora z dymkiem: najedź myszą i masz wartości wszystkich parametrów w tym momencie
- przy osi X wyświetla się **dokładny czas i obroty** w miejscu kursora — nie trzeba niczego zgadywać
- wykres w funkcji **czasu** albo w funkcji **obrotów**; przy obrotach program dzieli dane
  na przebiegi i domyślnie rysuje punkty, żeby linie nie tworzyły zygzaków
- „Normalizuj 0–100%”, gdy parametry mają bardzo różne wartości (obroty 0–6000, temperatura 80–90)
- zoom rolką, przesuwanie, eksport wykresu do PNG

**Tabela z kolorowaniem**
- im wyższa wartość, tym mocniejszy kolor komórki — wzrosty obrotów widać na pierwszy rzut oka
- zielone ▲ i czerwone ▼ pokazują wzrost lub spadek względem poprzedniego wiersza
- wiersz podświetla się razem z kursorem wykresu, kliknięcie w wiersz ustawia kursor

**Porównanie dwóch lub więcej logów** (`Ctrl+T`)
- wszystkie parametry z obu plików (także te obecne tylko w jednym z nich)
- log A linią ciągłą, log B przerywaną — te same parametry w tym samym kolorze
- tabela różnic: ile log B ma więcej lub mniej niż log A w każdym momencie
- statystyki (min/max/średnia, największa różnica) i przesunięcie czasowe logu B

**Obsługa logów VCDS**
- eksport CSV w wersji polskiej, angielskiej i niemieckiej (Windows-1250/1252, UTF-8)
- jedna, dwie albo trzy grupy pomiarowe; osobne kolumny czasu każdej grupy
- automatyczne rozpoznawanie parametrów i jednostek (`/min`, `%`, `ms`, `g/s`, `°C`, `°PGMP`, `mbar`…)

### Szybki start

1. Uruchom plik `.exe` (przy pierwszym starcie Windows może pokazać ostrzeżenie
   „Nieznany wydawca” — kliknij *Więcej informacji → Uruchom mimo to*)
2. `Ctrl+O` albo przeciągnij plik CSV z VCDS na okno programu
3. Najedź myszą na wykres — linia kursora pokaże wartości wszystkich parametrów
4. `Ctrl+T` — porównanie dwóch logów

Opis programu: [README](https://github.com/dras1911/VCDS-LogScope#readme)

---

Program jest darmowy i taki pozostanie. Jeśli oszczędza Ci czas w warsztacie,
możesz wesprzeć jego rozwój: **[☕ buymeacoffee.com/dras1911](https://buymeacoffee.com/dras1911)**

Autor: **Bartosz Dej** ([@dras1911](https://github.com/dras1911)) • licencja MIT
"""


def package_version() -> str:
    """Czyta wersję z vcds_viewer/__init__.py (bez importowania pakietu)."""
    text = (ROOT / "vcds_viewer" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("Nie znalazłem __version__ w vcds_viewer/__init__.py")
    return m.group(1)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def previous_tag(current: str) -> str:
    """Najbliższy wcześniejszy tag wersji (do listy zmian)."""
    tags = [t for t in git("tag", "--sort=-v:refname").splitlines() if t.startswith("v")]
    tags = [t for t in tags if t != current]
    return tags[0] if tags else ""


def changelog(version: str) -> str:
    """Opis zmian dla wersji: najpierw z CHANGELOG.md, w razie braku z historii gita."""
    text = ""
    path = ROOT / "CHANGELOG.md"
    if path.exists():
        text = path.read_text(encoding="utf-8")
    if text:
        m = re.search(rf"^##\s+{re.escape(version)}\b.*?$(.*?)(?=^##\s|\Z)",
                      text, re.M | re.S)
        if m and m.group(1).strip():
            return f"### Zmiany w wersji {version}\n\n{m.group(1).strip()}\n"

    tag = f"v{version}"
    prev = previous_tag(tag)
    rng = f"{prev}..HEAD" if prev else "-15"
    lines = [l.strip() for l in git("log", "--pretty=format:%s", rng).splitlines() if l.strip()]
    lines = [l for l in lines if not l.lower().startswith(("wersja ", "release "))]
    if not lines:
        return ""
    body = "\n".join(f"- {l}" for l in lines)
    header = f"### Zmiany w tej wersji (od {prev})" if prev else "### Zmiany w tej wersji"
    return f"{header}\n\n{body}\n"


def release_notes(version: str) -> str:
    notes = f"## VCDS LogScope {version}\n\n{DESCRIPTION}"
    changes = changelog(version)
    if changes:
        notes += f"\n{changes}"
    notes += """
### Pliki do pobrania

| Plik | System |
|---|---|
| **`VCDS-LogScope.exe`** | Windows 10 / 11 (64-bit) — zalecana, jeden plik |
| `VCDS-LogScope-Windows7.exe` | **Windows 7 / 8 / 8.1** i nowsze — dla starszych laptopów warsztatowych |
| `VCDS-LogScope-portable.zip` | Windows 10 / 11 — rozpakowany katalog, startuje szybciej |
"""
    return notes


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


def upload_asset(token: str, release_id: int, path: Path, asset_name: str | None = None,
                 replace: bool = True) -> str:
    """Wgrywa plik jako załącznik wydania (z opcją podmiany istniejącego)."""
    name = asset_name or path.name
    if replace:
        for asset in api(token, "GET", f"{API}/repos/{REPO}/releases/{release_id}/assets"):
            if asset["name"] in (name, name.replace(" ", "."), path.name, path.name.replace(" ", ".")):
                api(token, "DELETE", f"{API}/repos/{REPO}/releases/assets/{asset['id']}")
                print(f"Usunięto poprzedni załącznik: {asset['name']}")
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    url = f"{UPLOADS}/repos/{REPO}/releases/{release_id}/assets?name={urllib.parse.quote(name)}"
    print(f"Wgrywam {name} ({path.stat().st_size / 1e6:.1f} MB)…")
    res = api(token, "POST", url, payload=path.read_bytes(), content_type=ctype)
    return res.get("browser_download_url", "")


def main() -> int:
    args = sys.argv[1:]
    dry = "--dry-run" in args
    version = args[args.index("--version") + 1] if "--version" in args else package_version()
    tag = args[args.index("--tag") + 1] if "--tag" in args else f"v{version}"
    push_tag = "--no-tag-push" not in args

    assets: list[tuple[Path, str]] = [
        (ROOT / "dist" / "onefile" / "VCDS LogScope.exe", "VCDS-LogScope.exe"),
        (ROOT / "dist" / "legacy" / "VCDS LogScope.exe", "VCDS-LogScope-Windows7.exe"),
        (ROOT / "dist" / "VCDS-LogScope-portable.zip", "VCDS-LogScope-portable.zip"),
    ]
    if "--exe" in args:
        assets = [(Path(args[args.index("--exe") + 1]), "VCDS-LogScope.exe")]

    notes = release_notes(version)
    missing = [str(p) for p, _ in assets if not p.exists()]
    print(f"Wersja pakietu: {version}   tag: {tag}")
    if missing:
        print("Brakujące pliki (zostaną pominięte):")
        for m in missing:
            print("   ", m)
    if dry:
        print("\n--- treść wydania ---")
        print(notes)
        return 0

    if git("status", "--porcelain"):
        print("Uwaga: katalog roboczy nie jest czysty — wydanie powstanie z ostatniego commita.")

    # tag na bieżącym commicie (wydanie musi wskazywać konkretny stan kodu)
    if tag not in git("tag").splitlines():
        git("tag", "-a", tag, "-m", f"VCDS LogScope {version}")
        print(f"Utworzono tag {tag}")
    if push_tag:
        subprocess.run(["git", "push", "-q", "origin", tag], cwd=ROOT, check=False)
        print(f"Wypchnięto tag {tag}")

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
        release = api(token, "PATCH", f"{API}/repos/{REPO}/releases/{existing['id']}",
                      payload={"body": notes, "name": f"VCDS LogScope {version}"})
        print("Zaktualizowano opis wydania")
    else:
        release = api(token, "POST", f"{API}/repos/{REPO}/releases", payload={
            "tag_name": tag,
            "name": f"VCDS LogScope {version}",
            "body": notes,
            "draft": False,
            "prerelease": False,
        })
        print(f"Utworzono wydanie: {release.get('html_url')}")

    uploaded = []
    for path, name in assets:
        if path.exists():
            uploaded.append(upload_asset(token, release["id"], path, name))
        else:
            print(f"(pomijam brakujący plik: {path})")

    print("\nWydanie:", release.get("html_url"))
    print("Załączniki:")
    for url in uploaded:
        print(" ", url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
