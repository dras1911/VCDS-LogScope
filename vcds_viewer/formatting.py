"""Formatowanie liczb i czasu w stylu polskim (przecinek dziesiętny)."""

from __future__ import annotations

import math


def fmt_num(value: float | None, decimals: int | None = None) -> str:
    """Formatuje liczbę po polsku: 1 234,56."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return ""
    if decimals is None:
        a = abs(value)
        if a >= 1000:
            decimals = 0
        elif a >= 100:
            decimals = 1
        elif a >= 10:
            decimals = 2
        else:
            decimals = 3
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\u00a0").replace(".", ",")


def fmt_time(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return ""
    return f"{value:.{decimals}f}".replace(".", ",")


def fmt_delta(value: float | None, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    sign = "+" if value > 0 else ""
    return sign + fmt_num(value, decimals)


def fmt_int(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:,.0f}".replace(",", "\u00a0")


def plural_przebieg(n: int) -> str:
    """Odmiana rzeczownika „przebieg”: 1 przebieg, 2–4 przebiegi, 5+ przebiegów."""
    if n == 1:
        return "przebieg"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "przebiegi"
    return "przebiegów"
