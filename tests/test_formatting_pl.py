"""Testy formatowania po polsku (przecinek dziesiętny, odmiana „przebieg”).

Pilnują regresji: w komunikacie dopasowania w czasie i w pasku statusu liczyły
się z kropką („-5.04 s”, „zgodność 0.61”, „69.9 s”) zamiast po polsku.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.formatting import fmt_delta, fmt_num, fmt_time, plural_przebieg  # noqa: E402


def test_fmt_time_uses_comma():
    assert fmt_time(69.94, 1) == "69,9"
    assert fmt_time(69.94, 2) == "69,94"
    assert fmt_time(-5.04, 2) == "-5,04"


def test_fmt_num_uses_comma_and_nbsp():
    assert fmt_num(0.14, 2) == "0,14"
    assert fmt_num(4640.0, 0) == "4\u00a0640"


def test_fmt_delta_signs():
    assert fmt_delta(-5.04, 2) == "-5,04"
    assert fmt_delta(5.04, 2) == "+5,04"
    assert fmt_delta(0.0, 2) == "0,00"


def test_plural_przebieg():
    assert plural_przebieg(1) == "przebieg"
    assert plural_przebieg(2) == "przebiegi"
    assert plural_przebieg(3) == "przebiegi"
    assert plural_przebieg(4) == "przebiegi"
    assert plural_przebieg(5) == "przebiegów"
    assert plural_przebieg(7) == "przebiegów"
    assert plural_przebieg(12) == "przebiegów"
    assert plural_przebieg(13) == "przebiegów"
    assert plural_przebieg(22) == "przebiegi"
    assert plural_przebieg(25) == "przebiegów"
