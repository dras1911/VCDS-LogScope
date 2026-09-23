"""Porównanie dwóch lub więcej logów: nakładka na wykresie + tabela różnic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

from .chartview import LogChart, SeriesSpec
from .colors import color_for, color_map
from .formatting import fmt_delta, fmt_num, fmt_time
from .model import X_RPM, X_TIME, LogData
from .theme import Theme

# Style linii dla kolejnych logów (log A ciągła, log B przerywana, ...).
LINE_STYLES = [
    (Qt.SolidLine, "ciągła"),
    (Qt.DashLine, "przerywana"),
    (Qt.DotLine, "kropkowana"),
    (Qt.DashDotLine, "kreska-kropka"),
    (Qt.DashDotDotLine, "kreska-kropka-kropka"),
]
LOG_TAGS = ["A", "B", "C", "D", "E"]


@dataclass
class CompareParam:
    """Parametr wspólny dla porównywanych logów."""

    key: tuple
    name: str
    unit: str
    color: str
    series: dict[int, np.ndarray]     # indeks logu -> wartości (już na wspólnej siatce)
    group: str = ""                   # grupa pomiarowa w logu A


def interp_series(t: np.ndarray, y: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Interpolacja serii na wspólną siatkę czasu (z pominięciem NaN)."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(y) & np.isfinite(t)
    if mask.sum() < 2:
        return np.full(len(grid), np.nan)
    return np.interp(grid, t[mask], y[mask], left=np.nan, right=np.nan)


class CompareTableModel(QtCore.QAbstractTableModel):
    """Tabela różnic: wspólna siatka czasu, wartości bazowe i delty."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.grid: np.ndarray = np.array([])
        self.params: list[CompareParam] = []
        self.tags: list[str] = []
        self.heatmap = True
        self.show_b_values = False
        self._cols: list[tuple[str, int, int]] = []   # (rodzaj, indeks parametru, indeks logu)

    def set_data(self, grid: np.ndarray, params: list[CompareParam], tags: list[str]):
        self.beginResetModel()
        self.grid = grid
        self.params = params
        self.tags = tags
        self._build_cols()
        self.endResetModel()

    def set_show_b_values(self, on: bool):
        self.beginResetModel()
        self.show_b_values = on
        self._build_cols()
        self.endResetModel()

    def _build_cols(self):
        cols: list[tuple[str, int, int]] = [("time", -1, -1)]
        for p in range(len(self.params)):
            cols.append(("value", p, 0))
            for k in range(1, max(len(self.tags), 2)):
                if self.show_b_values:
                    cols.append(("value", p, k))
                cols.append(("delta", p, k))
        self._cols = cols

    # ------------------------------------------------------------ interfejs Qt
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.grid)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._cols)

    def headerText(self, section: int) -> str:
        typ, p, k = self._cols[section]
        if typ == "time":
            return "CZAS [s]"
        prm = self.params[p]
        unit = f" [{prm.unit}]" if prm.unit else ""
        group = f" (gr. {prm.group})" if prm.group else ""
        if typ == "value":
            return f"{prm.name}{group} — {self.tags[k]}{unit}"
        return f"Δ {self.tags[k]}−{self.tags[0]}{unit}"

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Vertical:
            if role == Qt.DisplayRole:
                return str(section + 1)
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return None
        if role == Qt.DisplayRole:
            return self.headerText(section)
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            typ, p, k = self._cols[section]
            if typ == "time":
                return "Wspólna siatka czasu (wartości interpolowane z obu logów)"
            prm = self.params[p]
            if typ == "value":
                return f"Wartość z logu {self.tags[k]}: {prm.name} [{prm.unit}]"
            return (f"Różnica: log {self.tags[k]} − log {self.tags[0]}\n{prm.name} [{prm.unit}]\n"
                    "zielone = wyższa wartość, czerwone = niższa")
        return None

    def data(self, index: QtCore.QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        typ, p, k = self._cols[c]
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if typ == "time":
            if role == Qt.DisplayRole:
                return fmt_time(float(self.grid[r]))
            if role == Qt.ForegroundRole:
                return QtGui.QColor(self.theme.text_dim)
            if role == Qt.BackgroundRole:
                return QtGui.QColor(self.theme.panel_alt)
            return None
        prm = self.params[p]
        if typ == "value":
            v = prm.series.get(k)
            if v is None or r >= len(v):
                return None
            if role == Qt.DisplayRole:
                return fmt_num(v[r])
            if role == Qt.BackgroundRole:
                return QtGui.QColor(self.theme.panel if r % 2 == 0 else self.theme.row_alt)
            return None
        # delta
        a = prm.series.get(0)
        b = prm.series.get(k)
        if a is None or b is None or r >= len(a) or r >= len(b):
            return None
        d = b[r] - a[r]
        if role == Qt.DisplayRole:
            return fmt_delta(d, 2 if abs(d) < 100 else 1)
        if role == Qt.BackgroundRole:
            if not self.heatmap or not np.isfinite(d):
                return None
            ref = self._delta_scale(prm)
            frac = min(1.0, abs(d) / ref) if ref > 0 else 0.0
            base = QtGui.QColor(self.theme.panel if r % 2 == 0 else self.theme.row_alt)
            target = QtGui.QColor("#12a150" if d >= 0 else "#d64545")
            k2 = (frac ** 0.7) * (0.85 if self.theme.is_dark else 0.7)
            return QtGui.QColor(
                int(base.red() + (target.red() - base.red()) * k2),
                int(base.green() + (target.green() - base.green()) * k2),
                int(base.blue() + (target.blue() - base.blue()) * k2),
            )
        if role == Qt.ForegroundRole:
            return QtGui.QColor(self.theme.text)
        return None

    def _delta_scale(self, prm: CompareParam) -> float:
        a = prm.series.get(0)
        if a is None:
            return 0.0
        worst = 0.0
        for k, b in prm.series.items():
            if k == 0 or b is None:
                continue
            d = np.abs(np.asarray(b) - np.asarray(a))
            d = d[np.isfinite(d)]
            if len(d):
                worst = max(worst, float(np.percentile(d, 98)))
        return worst or 1.0


class CompareView(QtWidgets.QWidget):
    """Widok porównania logów: nakładka serii + tabela różnic + statystyki."""

    cursorMoved = Signal(float, float, object)

    def __init__(self, logs: list[LogData], theme: Theme, parent=None):
        super().__init__(parent)
        self.logs = logs
        self.tags = LOG_TAGS[: len(logs)]
        self.theme = theme
        self.x_mode = X_TIME
        self.offset_b = 0.0
        self.param_checks: dict[tuple, bool] = {}
        self.log_checks: list[bool] = [True] * len(logs)

        self.chart = LogChart(theme, self)
        self.model = CompareTableModel(theme, self)
        self.table = QtWidgets.QTableView(self)
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(19)
        self.table.horizontalHeader().setDefaultSectionSize(110)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        self.stats = QtWidgets.QTableWidget(self)
        self.stats.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.stats.setAlternatingRowColors(True)
        self.stats.verticalHeader().setDefaultSectionSize(20)
        self.stats.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        self.panel = self._build_panel()
        self.toolbar = self._build_toolbar()

        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.addTab(self._wrap(self.chart), "Wykres porównawczy")
        self.tabs.addTab(self._delta_tab(), "Tabela różnic")
        self.tabs.addTab(self.stats, "Statystyki")

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.panel.setFixedWidth(300)
        body.addWidget(self.panel)
        body.addWidget(self.tabs, 1)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)
        root.addWidget(self.toolbar)
        root.addLayout(body, 1)

        self.chart.doubleClicked.connect(self.chart.fit)
        self.chart.cursorMoved.connect(self._on_cursor)
        self.chart.set_secondary_fn(self._secondary_text)
        self.refresh()

    def _wrap(self, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        return box

    def _delta_tab(self) -> QtWidgets.QWidget:
        """Zakładka tabeli różnic z opisem i opcją pokazania wartości logu B."""
        box = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(4)

        row = QtWidgets.QHBoxLayout()
        hint = QtWidgets.QLabel(
            "Δ = log B − log A  •  <span style='color:#12a150;'>zielone</span> = wyższa wartość "
            "w logu B, <span style='color:#d64545;'>czerwone</span> = niższa  •  "
            "wartości interpolowane do wspólnej siatki czasu"
        )
        hint.setObjectName("hint")
        row.addWidget(hint)
        row.addStretch(1)
        self.chk_b_values = QtWidgets.QCheckBox("Pokaż wartości logu B")
        self.chk_b_values.setToolTip("Dodaje kolumnę z surowymi wartościami drugiego logu obok delty")
        self.chk_b_values.toggled.connect(self._on_show_b_values)
        row.addWidget(self.chk_b_values)
        lay.addLayout(row)
        lay.addWidget(self.table)
        return box

    # ---------------------------------------------------------------- elementy
    def _build_toolbar(self) -> QtWidgets.QWidget:
        tb = QtWidgets.QWidget(self)
        lay = QtWidgets.QHBoxLayout(tb)
        lay.setContentsMargins(4, 2, 4, 0)
        lay.setSpacing(8)

        lay.addWidget(QtWidgets.QLabel("Oś X:"))
        self.cmb_x = QtWidgets.QComboBox()
        self.cmb_x.addItem("Czas [s]", X_TIME)
        self.cmb_x.addItem("Obroty [obr/min]", X_RPM)
        self.cmb_x.setFixedWidth(150)
        self.cmb_x.currentIndexChanged.connect(self._on_x_mode)
        lay.addWidget(self.cmb_x)

        self.chk_norm = QtWidgets.QCheckBox("Normalizuj 0–100%")
        self.chk_norm.setToolTip(
            "Przeskalowuje każdą serię do jej własnego zakresu — pozwala porównać kształty\n"
            "parametrów o bardzo różnych wartościach. Wartości w dymku pozostają rzeczywiste."
        )
        self.chk_norm.toggled.connect(self._on_normalize)
        lay.addWidget(self.chk_norm)

        self.lbl_hint = QtWidgets.QLabel("")
        self.lbl_hint.setObjectName("hint")
        self.lbl_hint.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        lay.addWidget(self.lbl_hint)

        lay.addWidget(QtWidgets.QLabel("Przesunięcie B [s]:"))
        self.spin_offset = QtWidgets.QDoubleSpinBox()
        self.spin_offset.setRange(-600, 600)
        self.spin_offset.setSingleStep(0.1)
        self.spin_offset.setDecimals(2)
        self.spin_offset.setFixedWidth(90)
        self.spin_offset.setToolTip(
            "Przesuwa w czasie log B (np. gdy logi startowały w różnych momentach jazdy)"
        )
        self.spin_offset.valueChanged.connect(self._on_offset)
        lay.addWidget(self.spin_offset)

        lay.addStretch(1)
        for text, tip, slot in (
            ("Dopasuj", "Dopasuj widok do danych", self.chart.fit),
            ("−", "Pomniejsz", lambda: self.chart.zoom(1.25)),
            ("+", "Powiększ", lambda: self.chart.zoom(0.8)),
            ("PNG", "Zapisz wykres jako PNG", self._export_png),
        ):
            b = QtWidgets.QPushButton(text)
            b.setToolTip(tip)
            b.setFixedHeight(26)
            b.clicked.connect(slot)
            lay.addWidget(b)
        return tb

    def _build_panel(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(6, 4, 4, 4)
        lay.setSpacing(4)

        head = QtWidgets.QLabel("Porównywane logi")
        head.setStyleSheet("font-weight:600;")
        lay.addWidget(head)
        self.log_list = QtWidgets.QListWidget()
        self.log_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.log_list.setTextElideMode(Qt.ElideMiddle)
        for i, log in enumerate(self.logs):
            style, style_name = LINE_STYLES[i % len(LINE_STYLES)]
            item = QtWidgets.QListWidgetItem(
                f"Log {self.tags[i]} — {log.meta.file_name}\nlinia {style_name}"
            )
            item.setSizeHint(QtCore.QSize(0, 34))
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, i)
            item.setToolTip(f"{log.path}\nlinia {style_name}\n{log.meta.summary()}")
            item.setIcon(self._line_icon(i))
            self.log_list.addItem(item)
        self.log_list.itemChanged.connect(self._on_log_toggled)
        self._fit_log_list()
        lay.addWidget(self.log_list)

        head2 = QtWidgets.QLabel("Parametry")
        head2.setStyleSheet("font-weight:600;")
        lay.addWidget(head2)
        btn_row = QtWidgets.QHBoxLayout()
        b_all = QtWidgets.QPushButton("Wszystkie")
        b_none = QtWidgets.QPushButton("Żadne")
        for b in (b_all, b_none):
            b.setFixedHeight(24)
            btn_row.addWidget(b)
        b_all.clicked.connect(lambda: self._set_all_params(True))
        b_none.clicked.connect(lambda: self._set_all_params(False))
        lay.addLayout(btn_row)

        self.param_list = QtWidgets.QListWidget()
        self.param_list.setUniformItemSizes(True)
        self.param_list.setIconSize(QtCore.QSize(12, 12))
        self.param_list.itemChanged.connect(self._on_param_toggled)
        lay.addWidget(self.param_list, 1)
        return box

    def _fit_log_list(self):
        """Dopasowuje wysokość listy logów do liczby pozycji (żeby nic nie było ucięte)."""
        self.log_list.doItemsLayout()
        h = sum(self.log_list.sizeHintForRow(i) for i in range(self.log_list.count()))
        h += 2 * self.log_list.frameWidth() + 6
        self.log_list.setFixedHeight(h)

    def _line_icon(self, log_index: int) -> QtGui.QIcon:
        color = QtGui.QColor("#9aa0a6")
        pix = QtGui.QPixmap(26, 12)
        pix.fill(Qt.transparent)
        p = QtGui.QPainter(pix)
        pen = QtGui.QPen(color, 2)
        pen.setStyle(LINE_STYLES[log_index % len(LINE_STYLES)][0])
        p.setPen(pen)
        p.drawLine(0, 6, 25, 6)
        p.end()
        return QtGui.QIcon(pix)

    # ------------------------------------------------------------------ dane
    def matched_params(self) -> list[tuple]:
        """Klucze parametrów wspólnych dla wszystkich logów."""
        keys = set(self.logs[0].match_index())
        for log in self.logs[1:]:
            keys &= set(log.match_index())
        ordered = [k for k in self.logs[0].match_index() if k in keys]
        return ordered

    def _common_grid(self) -> np.ndarray:
        """Wspólna siatka czasu: część wspólna zakresów, krok = najdrobniejszy krok logu."""
        starts, ends, steps = [], [], []
        for log in self.logs:
            t = np.concatenate([g.t for g in log.groups if len(g.t)]) if log.groups else np.array([])
            if not len(t):
                continue
            starts.append(float(np.min(t)))
            ends.append(float(np.max(t)))
            dt = np.diff(np.unique(t))
            steps.append(float(np.median(dt)) if len(dt) else 0.5)
        if not starts:
            return np.array([])
        t0, t1 = max(starts), min(ends)
        if t1 <= t0:
            t0, t1 = min(starts), max(ends)
        step = max(min(steps), 0.05)
        n = int((t1 - t0) / step) + 1
        if n > 20000:                      # bezpiecznik wydajności
            step = (t1 - t0) / 20000
            n = 20001
        return t0 + np.arange(n) * step

    def build_params(self) -> list[CompareParam]:
        grid = self._common_grid()
        out: list[CompareParam] = []
        colors = color_map(self.logs[0].channels, self.theme.is_dark)
        for key in self.matched_params():
            name, unit, occ = key
            channels = [log.find(key) for log in self.logs]
            if any(c is None for c in channels):
                continue
            series: dict[int, np.ndarray] = {}
            for i, ch in enumerate(channels):
                t = np.asarray(ch.t, dtype=float) + (self.offset_b if i == 1 else 0.0)
                series[i] = interp_series(t, np.asarray(ch.y, dtype=float), grid)
            out.append(
                CompareParam(
                    key=key,
                    name=channels[0].display_name,
                    unit=channels[0].unit,
                    color=colors.get(key, color_for(channels[0].name, channels[0].unit, occ)),
                    series=series,
                    group=channels[0].group,
                )
            )
        return out

    def refresh(self):
        """Przebudowuje wykres, tabelę różnic i statystyki."""
        self.grid = self._common_grid()
        self.params = self.build_params()

        # --- panel parametrów
        self.param_list.blockSignals(True)
        self.param_list.clear()
        for prm in self.params:
            group = f"  (gr. {prm.group})" if prm.group else ""
            unit = f"  [{prm.unit}]" if prm.unit else ""
            item = QtWidgets.QListWidgetItem(f"{prm.name}{group}{unit}")
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if self.param_checks.get(prm.key, True) else Qt.Unchecked)
            item.setData(Qt.UserRole, prm.key)
            item.setIcon(self._swatch(prm.color))
            item.setToolTip(f"{prm.name} [{prm.unit}] — grupa {prm.group} w logu A")
            self.param_list.addItem(item)
        self.param_list.blockSignals(False)

        # --- wykres
        specs: list[SeriesSpec] = []
        for prm in self.params:
            if not self.param_checks.get(prm.key, True):
                continue
            for i, log in enumerate(self.logs):
                if not self.log_checks[i]:
                    continue
                ch = log.find(prm.key)
                if ch is None or not ch.has_data:
                    continue
                x = log.x_for(ch, self.x_mode)
                if i == 1 and self.offset_b and self.x_mode == X_TIME:
                    x = np.asarray(x, dtype=float) + self.offset_b
                specs.append(
                    SeriesSpec(
                        sid=f"{prm.key}|{i}",
                        label=f"{ch.name} (Log {self.tags[i]})",
                        short=ch.name,
                        unit=ch.unit,
                        color=prm.color,
                        x=x,
                        y=ch.y,
                        style=LINE_STYLES[i % len(LINE_STYLES)][0],
                        width=1.7 if i == 0 else 1.5,
                        tag=f"Log {self.tags[i]}",
                        group=ch.group,
                    )
                )
        self.chart.set_x_axis(
            self.x_mode,
            "obr/min" if self.x_mode == X_RPM else "s",
            "Obroty silnika" if self.x_mode == X_RPM else "Czas",
        )
        self.chart.set_series(specs)

        # --- tabela różnic
        active = [p for p in self.params if self.param_checks.get(p.key, True)]
        self.model.set_data(self.grid, active, [self.tags[i] for i in range(len(self.logs))])
        fm = self.table.fontMetrics()
        for c in range(self.model.columnCount()):
            w = fm.horizontalAdvance(self.model.headerText(c)) + 28
            self.table.setColumnWidth(c, max(84, min(w, 300)))

        self._fill_stats(active)
        self._check_scales()

    def _swatch(self, color: str) -> QtGui.QIcon:
        pix = QtGui.QPixmap(12, 12)
        pix.fill(Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QBrush(QtGui.QColor(color)))
        p.setPen(QtGui.QPen(QtGui.QColor(color).darker(140), 1))
        p.drawRoundedRect(1, 1, 10, 10, 3, 3)
        p.end()
        return QtGui.QIcon(pix)

    def _fill_stats(self, params: list[CompareParam]):
        headers = ["Parametr", "Jedn."]
        for i in range(len(self.logs)):
            headers += [f"Min {self.tags[i]}", f"Max {self.tags[i]}", f"Średnia {self.tags[i]}"]
        headers += [f"Średnia Δ {self.tags[i]}−A" for i in range(1, len(self.logs))]
        headers += [f"Max |Δ| {self.tags[i]}−A" for i in range(1, len(self.logs))]

        self.stats.clear()
        self.stats.setColumnCount(len(headers))
        self.stats.setHorizontalHeaderLabels(headers)
        self.stats.setRowCount(len(params))
        for r, prm in enumerate(params):
            self.stats.setItem(r, 0, QtWidgets.QTableWidgetItem(prm.name))
            self.stats.setItem(r, 1, QtWidgets.QTableWidgetItem(prm.unit))
            c = 2
            for i in range(len(self.logs)):
                vals = prm.series.get(i)
                finite = vals[np.isfinite(vals)] if vals is not None else np.array([])
                if len(finite):
                    cells = (fmt_num(float(finite.min())), fmt_num(float(finite.max())),
                             fmt_num(float(finite.mean())))
                else:
                    cells = ("", "", "")
                for text in cells:
                    self.stats.setItem(r, c, QtWidgets.QTableWidgetItem(text))
                    c += 1
            a = prm.series.get(0)
            for i in range(1, len(self.logs)):
                b = prm.series.get(i)
                if a is None or b is None:
                    c += 2
                    continue
                d = np.asarray(b) - np.asarray(a)
                finite = d[np.isfinite(d)]
                self.stats.setItem(r, c, QtWidgets.QTableWidgetItem(
                    fmt_delta(float(finite.mean()), 2) if len(finite) else ""))
                self.stats.setItem(r, c + 1, QtWidgets.QTableWidgetItem(
                    fmt_num(float(np.abs(finite).max())) if len(finite) else ""))
                c += 2
        self.stats.resizeColumnsToContents()

    # ------------------------------------------------------------------ akcje
    def _on_param_toggled(self, item: QtWidgets.QListWidgetItem):
        key = item.data(Qt.UserRole)
        if key is None:
            return
        self.param_checks[key] = item.checkState() == Qt.Checked
        self.refresh()

    def _on_log_toggled(self, item: QtWidgets.QListWidgetItem):
        i = item.data(Qt.UserRole)
        if i is None:
            return
        self.log_checks[int(i)] = item.checkState() == Qt.Checked
        self.refresh()

    def _set_all_params(self, checked: bool):
        for i in range(self.param_list.count()):
            item = self.param_list.item(i)
            key = item.data(Qt.UserRole)
            if key is not None:
                self.param_checks[key] = checked
        self.refresh()

    def _on_show_b_values(self, checked: bool):
        self.model.set_show_b_values(checked)
        fm = self.table.fontMetrics()
        for c in range(self.model.columnCount()):
            w = fm.horizontalAdvance(self.model.headerText(c)) + 28
            self.table.setColumnWidth(c, max(84, min(w, 300)))

    def _on_normalize(self, on: bool):
        self.chart.set_normalized(on)
        self._check_scales()

    def _check_scales(self):
        """Podpowiada normalizację, gdy rozpiętości porównywanych parametrów bardzo się różnią."""
        spans = []
        for prm in self.params:
            v = prm.series.get(0)
            if v is None:
                continue
            finite = v[np.isfinite(v)]
            if len(finite):
                spans.append(float(finite.max() - finite.min()))
        if not spans or self.chk_norm.isChecked():
            self.lbl_hint.setText("")
            return
        spans.sort()
        ratio = spans[-1] / max(spans[0], 1e-9)
        self.lbl_hint.setText(
            "Wskazówka: zakresy parametrów różnią się bardzo — włącz „Normalizuj 0–100%”, "
            "aby porównać kształty wszystkich serii"
            if ratio > 25 else ""
        )

    def _on_x_mode(self):
        self.x_mode = self.cmb_x.currentData()
        self.refresh()

    def _on_offset(self, value: float):
        self.offset_b = float(value)
        self.refresh()

    def _on_cursor(self, x: float):
        self.cursorMoved.emit(x, float("nan"), self)

    def _secondary_text(self, x: float) -> str:
        """Obroty przy osi czasu (na podstawie logu A) albo czas przy osi obrotów."""
        base = self.logs[0]
        if self.x_mode == X_TIME:
            rpm = base.rpm_nearest(x)
            return f"Log {self.tags[0]}: {fmt_num(rpm)} obr/min" if rpm is not None else ""
        series = base.rpm_series()
        if series is None:
            return ""
        rt, ry = series
        order = np.argsort(ry)
        t = float(np.interp(x, ry[order], rt[order]))
        return f"Log {self.tags[0]}: {fmt_num(t, 2)} s"

    def _export_png(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Zapisz wykres porównawczy jako PNG", "porownanie.png", "Obraz PNG (*.png)"
        )
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            self.chart.export_png(path)

    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.chart.refresh_theme(theme)
        self.model.theme = theme
        self.model.beginResetModel()
        self.model.endResetModel()
        self.refresh()
