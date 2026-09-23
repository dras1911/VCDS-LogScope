"""Paleta kolorów — odwzorowanie stylu TuneZilla (kolor per parametr).

Kolory przypisywane są rolami: pierwszy parametr danej rodziny dostaje kolor
„wzorcowy” z TuneZilla (napięcie szare, obciążenie czerwone, obroty żółte...),
a kolejne parametry tej samej rodziny — następne wolne kolory, tak aby żadne
dwie serie na wykresie nie miały identycznego koloru.
"""

from __future__ import annotations

import re

COLOR_GRAY = "#9aa0a6"
COLOR_RED = "#e5484d"
COLOR_ORANGE = "#f5a623"
COLOR_GREEN = "#12a150"
COLOR_YELLOW = "#e8d44d"
COLOR_PINK = "#f06ba8"
COLOR_LIGHT_PINK = "#ffb0cd"
COLOR_DARK = "#c8cdd4"
COLOR_MAGENTA = "#b23ad6"
COLOR_VIOLET = "#8b5cf6"
COLOR_CYAN = "#31c8d8"
COLOR_BLUE = "#4c8df6"
COLOR_TEAL = "#2bb673"
COLOR_BROWN = "#b98a5b"
COLOR_LIME = "#a3d34f"

FALLBACK_PALETTE = [
    COLOR_CYAN, COLOR_ORANGE, COLOR_VIOLET, COLOR_TEAL, COLOR_BLUE,
    COLOR_RED, COLOR_LIME, COLOR_PINK, COLOR_BROWN, COLOR_MAGENTA,
]

# Rodzina parametru -> uporządkowana lista kolorów (pierwszy = wzorcowy TuneZilla).
_FAMILIES: list[tuple[tuple[str, ...], list[str]]] = [
    (("napięcie", "napiecie", "voltage", "batterie", "battery"), [COLOR_GRAY, COLOR_BLUE, COLOR_TEAL]),
    (("obciążenie", "obciazenie", "load"), [COLOR_RED, COLOR_ORANGE, COLOR_LIGHT_PINK]),
    (("czas wtrysku", "wtrysk", "injection", "einspritz"), [COLOR_ORANGE, COLOR_BROWN, COLOR_LIME]),
    (("masowe", "mass air", "maf", "luftmasse", "przepływ", "przeplyw"), [COLOR_GREEN, COLOR_TEAL, COLOR_LIME]),
    (("obroty", "engine speed", "drehzahl", "rpm"), [COLOR_YELLOW, COLOR_ORANGE, COLOR_LIME, COLOR_CYAN]),
    (("temperatura", "temperature", "temp"), [COLOR_PINK, COLOR_BROWN, COLOR_CYAN, COLOR_LIME]),
    (("kąt", "kat ", "ign", "timing", "zünd", "zund"), [COLOR_MAGENTA, COLOR_VIOLET, COLOR_PINK]),
    (("lambda", "afr", "sonda"), [COLOR_CYAN, COLOR_LIME, COLOR_BLUE]),
    (("ciśnienie", "cisnienie", "pressure", "druck", "boost", "ładowanie", "ladowanie"),
     [COLOR_BLUE, COLOR_CYAN, COLOR_VIOLET]),
    (("przepustnic", "throttle", "drossel"), [COLOR_TEAL, COLOR_GREEN, COLOR_LIME]),
    (("droga", "dystans", "distance"), [COLOR_BROWN, COLOR_GRAY, COLOR_TEAL]),
]


def _family_colors(name: str) -> list[str]:
    n = re.sub(r"\s+", " ", (name or "").strip().lower())
    for keys, colors in _FAMILIES:
        if any(k in n for k in keys):
            return colors
    return FALLBACK_PALETTE


def color_for(name: str, unit: str = "", occurrence: int = 0) -> str:
    """Kolor wzorcowy dla parametru (bez gwarancji unikalności)."""
    colors = _family_colors(name)
    return colors[min(occurrence, len(colors) - 1)]


def darken(color: str, factor: float = 0.78) -> str:
    """Przyciemnia kolor — używane w motywie jasnym, gdzie jasne barwy giną na białym tle."""
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


def theme_color(color: str, dark: bool) -> str:
    """Dopasowuje kolor serii do motywu (w jasnym motywie kolory są ciemniejsze)."""
    return color if dark else darken(color)


def color_map(channels, dark: bool = True) -> dict:
    """Przypisuje unikalny kolor każdemu kanałowi (klucz = match_key)."""
    used: set[str] = set()
    out: dict = {}
    for ch in channels:
        key = getattr(ch, "match_key", None)
        if key is None:
            continue
        picked = None
        for cand in _family_colors(getattr(ch, "name", "")) + FALLBACK_PALETTE:
            if cand not in used:
                picked = cand
                break
        if picked is None:  # wszystkie kolory zajęte — powtarzamy paletę
            picked = FALLBACK_PALETTE[len(used) % len(FALLBACK_PALETTE)]
        used.add(picked)
        out[key] = theme_color(picked, dark)
    return out


def hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return (r, g, b, alpha)


def lighten(color: str, factor: float = 0.55) -> str:
    """Rozjaśnia kolor (mieszanie z bielą) — używane w podświetleniach."""
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"
