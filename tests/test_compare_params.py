"""Testy porównania logów: lista parametrów i obsługa parametrów z jednego logu."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcds_viewer.compare import CompareView  # noqa: E402
from vcds_viewer.parser import parse_log  # noqa: E402
from vcds_viewer.theme import DARK  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
SAMPLE = DATA / "przyklad.csv"


@pytest.fixture(scope="module")
def app():
    from vcds_viewer.qt import QtWidgets

    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    yield instance


@pytest.fixture(scope="module")
def view(app):
    if not SAMPLE.exists():
        pytest.skip("brak pliku przykładowego")
    logs = [parse_log(SAMPLE), parse_log(SAMPLE)]
    v = CompareView(logs, DARK)
    v.resize(1400, 800)
    v.ensurePolished()
    return v


def test_all_params_include_those_from_single_log(view):
    """Parametr obecny tylko w jednym logu też ma być na liście."""
    params = view.build_params()
    assert params, "lista parametrów nie może być pusta"
    assert all(p.logs for p in params), "każdy parametr musi wskazywać, gdzie występuje"
    keys = [p.key for p in params]
    assert len(keys) == len(set(keys)), "bez duplikatów"


def test_params_from_both_logs_are_common(view):
    """Dla dwóch identycznych logów wszystkie parametry są wspólne."""
    params = view.build_params()
    assert all(p.common for p in params)
    assert all(len(p.logs) == 2 for p in params)


def _log_without_first_channel(log):
    """Kopia logu bez pierwszego kanału liczbowego (symuluje inny zestaw grup)."""
    import copy

    from vcds_viewer.model import LogData

    drop = log.numeric_channels[0].match_key
    groups = copy.deepcopy(log.groups)
    for g in groups:
        g.channels = [c for c in g.channels if c.match_key != drop]
    return LogData(path=log.path, meta=log.meta, groups=groups)


def test_parameter_present_in_one_log_is_marked(view):
    """Symulujemy log bez jednego parametru — ma się pojawić jako „tylko A/B”."""
    logs = view.logs
    reduced = _log_without_first_channel(logs[0])
    v2 = CompareView([logs[0], reduced], DARK)
    v2.resize(1400, 800)
    params = v2.build_params()
    missing_key = logs[0].numeric_channels[0].match_key
    entry = next((p for p in params if p.key == missing_key), None)
    assert entry is not None, "parametr z jednego logu nie może zniknąć z listy"
    assert entry.common is False
    assert entry.logs == [0]
    assert len(params) > len([p for p in params if p.common])


def test_diff_table_has_columns_for_single_log_params(view):
    """Tabela różnic nie może się wywalać na parametrach z jednego logu."""
    logs = view.logs
    reduced = _log_without_first_channel(logs[0])
    v2 = CompareView([logs[0], reduced], DARK)
    v2.resize(1400, 800)
    model = v2.model
    assert model.columnCount() > 0
    for c in range(model.columnCount()):
        model.headerText(c)
    for r in (0, 1, model.rowCount() - 1):
        for c in range(model.columnCount()):
            model.data(model.index(r, c))
