"""Buduje przenośną wersję .exe (PyInstaller) i tworzy skrót na pulpicie.

Użycie:
    .venv/Scripts/python.exe tools/build_exe.py            # build + skrót
    .venv/Scripts/python.exe tools/build_exe.py --no-shortcut
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "VCDS LogScope"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PY_LEGACY = ROOT / ".venv38" / "Scripts" / "python.exe"

# Moduły Qt, których aplikacja nie używa — wykluczone, by zmniejszyć rozmiar paczki.
# UWAGA: NIE wykluczać PySide6.QtOpenGL ani PySide6.QtOpenGLWidgets — pyqtgraph
# importuje je bezwarunkowo (pyqtgraph/Qt/OpenGLHelpers.py) i aplikacja nie wystartuje.
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "tkinter", "matplotlib", "pandas", "scipy", "IPython", "pytest",
]

# Wersja dla Windows 7/8 (Python 3.8 + Qt 5.15). Te same wykluczenia, nazwy PySide2.
EXCLUDES_LEGACY = [
    "PySide2.QtWebEngineCore", "PySide2.QtWebEngineWidgets", "PySide2.QtWebEngine",
    "PySide2.QtQuick", "PySide2.QtQml", "PySide2.QtQuickWidgets", "PySide2.QtQuickControls2",
    "PySide2.Qt3DCore", "PySide2.Qt3DRender", "PySide2.Qt3DInput", "PySide2.Qt3DLogic",
    "PySide2.Qt3DAnimation", "PySide2.Qt3DExtras", "PySide2.QtCharts",
    "PySide2.QtDataVisualization", "PySide2.QtMultimedia", "PySide2.QtMultimediaWidgets",
    "PySide2.QtBluetooth", "PySide2.QtNfc", "PySide2.QtPositioning", "PySide2.QtSensors",
    "PySide2.QtSerialPort", "PySide2.QtSql", "PySide2.QtTest", "PySide2.QtDesigner",
    "PySide2.QtHelp", "PySide2.QtLocation", "PySide2.QtRemoteObjects", "PySide2.QtScxml",
    "PySide2.QtStateMachine", "PySide2.QtTextToSpeech", "PySide2.QtWebChannel",
    "PySide2.QtWebSockets", "PySide2.QtXmlPatterns",
    "tkinter", "matplotlib", "pandas", "scipy", "IPython", "pytest",
]


def make_icon() -> Path:
    """Rysuje ikonę aplikacji i zapisuje ją jako .ico (przez Qt + Pillow)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    from vcds_viewer.qt import QtWidgets  # noqa: PLC0415

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from vcds_viewer.mainwindow import app_icon  # noqa: PLC0415

    png = BUILD / "icon_256.png"
    BUILD.mkdir(parents=True, exist_ok=True)
    app_icon().pixmap(256, 256).save(str(png))
    ico = BUILD / "icon.ico"
    try:
        from PIL import Image  # noqa: PLC0415

        img = Image.open(png)
        img.save(ico, format="ICO",
                 sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"Ikona: {ico}")
    except Exception as exc:  # pragma: no cover
        print(f"Uwaga: nie udało się utworzyć .ico ({exc}) — build bez ikony")
        return Path()
    return ico


def build(icon: Path, onefile: bool = False, legacy: bool = False) -> Path:
    """Uruchamia PyInstaller.

    onefile=True → jeden plik .exe, False → katalog (szybszy start).
    legacy=True  → build dla Windows 7/8 (Python 3.8 + Qt 5.15, PyInstaller 5).
    """
    python = PY_LEGACY if legacy else PY
    if legacy and not python.exists():
        raise SystemExit(
            f"Brak środowiska dla wersji Windows 7: {python}\n"
            "Utwórz je:  uv venv --python 3.8 .venv38 && "
            "uv pip install --python .venv38/Scripts/python.exe PySide2==5.15.2.1 "
            "pyqtgraph==0.13.3 'numpy<1.25' pyinstaller==5.13.2"
        )
    tag = "legacy" if legacy else ("onefile" if onefile else "onedir")
    out_dir = DIST if not (onefile or legacy) else (DIST / tag)
    cmd = [
        str(python), "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--onefile" if (onefile or legacy) else "--onedir",
        "--name", APP_NAME,
        "--distpath", str(out_dir),
        "--workpath", str(BUILD / f"pyinstaller_{tag}"),
        "--specpath", str(BUILD / f"spec_{tag}"),
    ]
    if icon and icon.exists():
        cmd += ["--icon", str(icon)]
    for mod in (EXCLUDES_LEGACY if legacy else EXCLUDES):
        cmd += ["--exclude-module", mod]
    cmd += ["--paths", str(ROOT)]
    cmd.append(str(ROOT / "vcds_logscope.py"))

    print(f"PyInstaller: budowanie paczki ({tag})…")
    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        raise SystemExit(f"PyInstaller zakończył się błędem (kod {res.returncode})")
    exe = (out_dir / APP_NAME / f"{APP_NAME}.exe") if tag == "onedir" else (out_dir / f"{APP_NAME}.exe")
    if not exe.exists():
        raise SystemExit(f"Nie znaleziono pliku wynikowego: {exe}")
    return exe


def smoke_test(exe: Path) -> bool:
    """Uruchamia autotest spakowanej aplikacji i sprawdza wynik.

    Sprawdza dwie rzeczy: tryb bezokienkowy (--selftest) oraz PEŁNY start GUI
    z pętlą zdarzeń (--selftest-gui) — to drugie łapie błędy typu `exec_()` vs `exec()`.
    """
    out = BUILD / "selftest_exe"
    out.mkdir(parents=True, exist_ok=True)
    sample = ROOT / "tests" / "data" / "przyklad.csv"
    base = [str(exe)]
    if sample.exists():
        base.append(str(sample))

    print("Autotest paczki (bez okna):", exe.name, "…")
    res = subprocess.run(base + ["--selftest", str(out)], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=300)
    report = out / "selftest_report.txt"
    text = report.read_text(encoding="utf-8") if report.exists() else (res.stdout or res.stderr or "")
    print(text.strip()[-400:])
    ok_headless = res.returncode == 0 and "SELFTEST: OK" in text

    print("Autotest paczki (pełne GUI):", exe.name, "…")
    res_gui = subprocess.run(base + ["--selftest-gui"], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=300)
    ok_gui = res_gui.returncode == 0
    if not ok_gui:
        print("  BŁĄD GUI:", (res_gui.stderr or res_gui.stdout or "")[-500:])

    print(f"Autotest: {'OK' if (ok_headless and ok_gui) else 'BŁĄD'} "
          f"(bez okna: {'OK' if ok_headless else 'BŁĄD'}, GUI: {'OK' if ok_gui else 'BŁĄD'})")
    return ok_headless and ok_gui


def make_shortcut(exe: Path) -> None:
    """Tworzy skrót na pulpicie użytkownika (PowerShell + WScript.Shell)."""
    desktop = Path(os.path.expanduser("~")) / "Desktop"
    lnk = desktop / f"{APP_NAME}.lnk"
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk}'); "
        f"$s.TargetPath = '{exe}'; "
        f"$s.WorkingDirectory = '{exe.parent}'; "
        f"$s.IconLocation = '{exe}'; "
        "$s.Description = 'Czytnik logów VCDS'; "
        "$s.Save()"
    )
    res = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                         capture_output=True, text=True)
    if res.returncode == 0 and lnk.exists():
        print(f"Skrót na pulpicie: {lnk}")
    else:
        print(f"Nie udało się utworzyć skrótu: {res.stderr.strip() or res.stdout.strip()}")


def main() -> int:
    onefile_only = "--onefile" in sys.argv
    legacy_only = "--legacy" in sys.argv
    both = "--all" in sys.argv
    if not PY.exists():
        raise SystemExit(f"Brak interpretera w {PY} — utwórz środowisko .venv")
    icon = make_icon()

    results: list[tuple[Path, bool]] = []
    if not (onefile_only or legacy_only) or both:
        exe = build(icon, onefile=False)
        size_mb = sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file()) / 1e6
        print(f"\nWersja katalogowa: {exe}  ({size_mb:.0f} MB)")
        results.append((exe, smoke_test(exe)))
    if onefile_only or both:
        exe1 = build(icon, onefile=True)
        print(f"\nWersja jednoplikowa: {exe1}  ({exe1.stat().st_size / 1e6:.0f} MB)")
        results.append((exe1, smoke_test(exe1)))
    if legacy_only or both:
        exe2 = build(icon, legacy=True)
        print(f"\nWersja dla Windows 7/8: {exe2}  ({exe2.stat().st_size / 1e6:.0f} MB)")
        results.append((exe2, smoke_test(exe2)))

    if results and "--no-shortcut" not in sys.argv and not (onefile_only or legacy_only):
        make_shortcut(results[0][0])
    ok = all(r[1] for r in results)
    print("\nPodsumowanie:", ", ".join(f"{p.name}: {'OK' if o else 'BŁĄD'}" for p, o in results))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
