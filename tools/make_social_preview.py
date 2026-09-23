"""Tworzy kartę podglądu repozytorium (social preview) 1280x640.

Sam robi zrzut programu (tryb „tylko wykres”, motyw ciemny), więc nie zależy od
plików docs/. Wgrywa się ją ręcznie: GitHub → Settings → Social preview → Upload an image.

Użycie: .venv/Scripts/python.exe tools/make_social_preview.py [plik_wyjsciowy]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("VCDS_LOGSCOPE_SETTINGS", "VCDS-LogScope-test")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "social-preview.png"
SAMPLE = ROOT / "tests" / "data" / "przyklad.csv"

W, H = 1280, 640
BG_TOP, BG_BOTTOM = (17, 19, 23), (30, 35, 44)
ACCENT, GREEN, RED = (76, 141, 246), (46, 190, 108), (235, 90, 95)
TEXT, DIM = (238, 240, 243), (160, 167, 175)
FONT_DIR = Path("C:/Windows/Fonts")


def font(name: str, size: int):
    from PIL import ImageFont

    for candidate in (FONT_DIR / name, FONT_DIR / "segoeui.ttf", FONT_DIR / "arial.ttf"):
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_screenshot() -> Path | None:
    """Zrzut okna programu w trybie „tylko wykres” (ciemny motyw)."""
    from vcds_viewer.qt import QtWidgets

    from vcds_viewer.mainwindow import MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    win = MainWindow()
    win.resize(1560, 620)
    win.ensurePolished()
    QtWidgets.QApplication.processEvents()
    if not SAMPLE.exists():
        return None
    win.open_path(str(SAMPLE))
    QtWidgets.QApplication.processEvents()
    view = win.tabs.currentWidget()
    win.set_view_mode("chart")
    QtWidgets.QApplication.processEvents()
    view.chart.set_cursor_x(31.5, emit=True)
    QtWidgets.QApplication.processEvents()
    shot = ROOT / "build" / "shots" / "hero.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    win.grab().save(str(shot))
    win.close()
    return shot


def main() -> int:
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(canvas)
    for y in range(H):
        k = y / H
        draw.line([(0, y), (W, y)], fill=tuple(
            int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * k) for i in range(3)))
    draw.rectangle([0, 0, W, 5], fill=ACCENT)

    f_title, f_sub, f_legend = font("segoeuib.ttf", 66), font("segoeui.ttf", 26), font("segoeui.ttf", 21)
    draw.text((60, 40), "VCDS LogScope", font=f_title, fill=TEXT)
    draw.text((62, 122), "Czytelne logi z VCDS / VAG-COM — darmowy program dla Windows",
              font=f_sub, fill=DIM)

    x = 62
    for color, label in ((GREEN, "wszystkie parametry"), (RED, "kolorowana tabela"),
                         (ACCENT, "porównanie logów")):
        draw.line([(x, 172), (x + 26, 172)], fill=color, width=5)
        draw.text((x + 36, 158), label, font=f_legend, fill=DIM)
        x += 36 + int(draw.textlength(label, font=f_legend)) + 34

    shot_path = render_screenshot()
    if shot_path and shot_path.exists():
        shot = Image.open(shot_path).convert("RGB")
        # obcinamy menu i pasek narzędzi — zostaje sam wykres z tabelą
        top = int(shot.height * 0.135)
        shot = shot.crop((0, top, shot.width, shot.height))
        # skalujemy tak, żeby CAŁY zrzut zmieścił się na karcie (nic nie może być ucięte)
        box_w, box_h = W - 120, H - 214 - 18
        scale = min(box_w / shot.width, box_h / shot.height)
        shot = shot.resize((max(1, int(shot.width * scale)), max(1, int(shot.height * scale))),
                           Image.LANCZOS)
        mask = Image.new("L", shot.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], 12, fill=255)
        x0, y0 = (W - shot.width) // 2, 214
        canvas.paste(shot, (x0, y0), mask)
        draw.rounded_rectangle([x0, y0, x0 + shot.width, y0 + shot.height], 12,
                               outline=(62, 68, 78), width=2)
    else:
        draw.text((60, 300), "(nie udało się zrobić zrzutu)", font=f_legend, fill=DIM)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, "PNG")
    print(f"zapisano: {OUT}  ({canvas.width}x{canvas.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
