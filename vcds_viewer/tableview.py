"""Tabela logu z kolorowaniem narastającym (heatmapa) i podświetlaniem wiersza kursora."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from .qt import QAction, Qt, QtCore, QtGui, QtWidgets, Signal

from .colors import color_map
from .formatting import fmt_num, fmt_time
from .model import Channel, LogData
from .theme import Theme


@dataclass
class TableColumn:
    """Opis kolumny tabeli."""

    group: str
    group_id: str
    title: str          # nazwa parametru
    unit: str
    channel: Optional[Channel]
    is_time: bool = False
    col_min: float = 0.0
    col_max: float = 1.0

    @property
    def group_title(self) -> str:
        return f"Grupa {self.group}: {self.group_id}"


class LogTableModel(QtCore.QAbstractTableModel):
    """Model danych tabeli: bloki grup (CZAS + parametry) obok siebie."""

    def __init__(self, log: LogData, theme: Theme, parent=None):
        super().__init__(parent)
        self.log = log
        self.theme = theme
        self.columns: list[TableColumn] = []
        self.n_rows = log.n_rows
        self.heatmap = True
        self.heatmap_color = "#12a150"     # klasyczna zielona skala
        self.show_deltas = True
        self.delta_threshold = 0.01        # 1% zakresu kolumny
        self.hover_rows: dict[str, int] = {}   # grupa -> podświetlony wiersz
        self.colors = color_map(log.channels, theme.is_dark)
        self._build_columns()

    def color_of(self, col: TableColumn) -> str:
        if col.channel is None:
            return self.theme.text_dim
        return self.colors.get(col.channel.match_key, self.theme.text_dim)

    # ------------------------------------------------------------------ budowa
    def _build_columns(self):
        self.columns.append(
            TableColumn(group="", group_id="", title="#", unit="", channel=None, is_time=False)
        )
        for grp in self.log.groups:
            self.columns.append(
                TableColumn(
                    group=grp.letter, group_id=grp.group_id, title="CZAS",
                    unit="s", channel=None, is_time=True,
                )
            )
            for ch in grp.channels:
                lo = hi = 0.0
                if ch.has_data:
                    lo, hi = float(np.nanmin(ch.y)), float(np.nanmax(ch.y))
                self.columns.append(
                    TableColumn(
                        group=grp.letter, group_id=grp.group_id, title=ch.display_name,
                        unit=ch.unit, channel=ch, col_min=lo, col_max=hi,
                    )
                )
        self.n_rows = max((g.n_samples for g in self.log.groups), default=0)

    def set_theme(self, theme: Theme):
        self.theme = theme
        self.colors = color_map(self.log.channels, theme.is_dark)
        self._rebuild_view()

    def _rebuild_view(self):
        self.beginResetModel()
        self.endResetModel()

    # ------------------------------------------------------------- interfejs Qt
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else self.n_rows

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Vertical:
            if role == Qt.DisplayRole:
                return str(section + 1)
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return None
        col = self.columns[section]
        if role == Qt.DisplayRole:
            unit = f" [{col.unit}]" if col.unit and not col.is_time else ""
            return f"{col.title}{unit}"
        if role == Qt.ToolTipRole:
            if col.channel is None:
                return None
            lo, hi = col.col_min, col.col_max
            return f"{col.group_title}\n{col.title} [{col.unit}]\nzakres: {fmt_num(lo)} … {fmt_num(hi)}"
        return None

    def data(self, index: QtCore.QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        col = self.columns[c]
        if role == Qt.DisplayRole:
            return self._text(r, col)
        if role == Qt.TextAlignmentRole:
            return int((Qt.AlignLeft if c == 0 else Qt.AlignRight) | Qt.AlignVCenter)
        if role == Qt.BackgroundRole:
            return self._background(r, col)
        if role == Qt.ForegroundRole:
            return self._foreground(r, col)
        if role == Qt.FontRole:
            f = QtGui.QFont()
            if c == 0:
                f.setPointSizeF(8.5)
            if col.is_time:
                f.setPointSizeF(8.5)
            return f
        if role == Qt.ToolTipRole:
            return self._tooltip(r, col)
        return None

    # ------------------------------------------------------------------ treść
    def _value(self, r: int, col: TableColumn):
        if col.is_time:
            t = self._group_time(col.group)
            return t[r] if t is not None and r < len(t) else None
        ch = col.channel
        if ch is None or ch.y is None or r >= len(ch.y):
            return None
        v = ch.y[r]
        return None if np.isnan(v) else float(v)

    def _group_time(self, letter: str) -> Optional[np.ndarray]:
        for g in self.log.groups:
            if g.letter == letter:
                return g.t
        return None

    def _text(self, r: int, col: TableColumn) -> str:
        if col.group == "":
            return str(r + 1)
        if col.is_time:
            return fmt_time(self._value(r, col), 2)
        ch = col.channel
        if ch is None:
            return ""
        if not ch.numeric or ch.y is None:
            return ch.raw[r] if r < len(ch.raw) else ""
        v = self._value(r, col)
        if v is None:
            return ""
        text = fmt_num(v)
        if self.show_deltas:
            arrow = self._arrow(r, col, v)
            if arrow:
                text = f"{text} {arrow}"
        return text

    def _arrow(self, r: int, col: TableColumn, value: float) -> str:
        if r == 0 or col.channel is None or col.channel.y is None:
            return ""
        prev = col.channel.y[r - 1] if r - 1 < len(col.channel.y) else None
        if prev is None or np.isnan(prev):
            return ""
        span = col.col_max - col.col_min
        if span <= 0:
            return ""
        delta = (value - prev) / span
        if delta > self.delta_threshold:
            return "▲"
        if delta < -self.delta_threshold:
            return "▼"
        return ""

    def _norm(self, r: int, col: TableColumn) -> Optional[float]:
        v = self._value(r, col)
        if v is None:
            return None
        span = col.col_max - col.col_min
        if span <= 0:
            return 0.5
        return max(0.0, min(1.0, (v - col.col_min) / span))

    def _background(self, r: int, col: TableColumn):
        t = self.theme
        if col.group == "":
            return QtGui.QColor(t.panel_alt)
        if col.is_time:
            return QtGui.QColor(t.panel_alt)
        hovered = self.hover_rows.get(col.group) == r
        base = QtGui.QColor(t.row_alt if r % 2 else t.panel)
        if self.heatmap and col.channel is not None and col.channel.has_data:
            frac = self._norm(r, col)
            if frac is not None:
                target = QtGui.QColor(self.heatmap_color)
                # nasycenie skalujemy tak, by niskie wartości były subtelne
                k = (frac ** 0.85) * (0.85 if t.is_dark else 0.7)
                base = QtGui.QColor(
                    int(base.red() + (target.red() - base.red()) * k),
                    int(base.green() + (target.green() - base.green()) * k),
                    int(base.blue() + (target.blue() - base.blue()) * k),
                )
        if hovered:
            accent = QtGui.QColor(t.accent)
            k = 0.40
            base = QtGui.QColor(
                int(base.red() * (1 - k) + accent.red() * k),
                int(base.green() * (1 - k) + accent.green() * k),
                int(base.blue() * (1 - k) + accent.blue() * k),
            )
        return base

    def _foreground(self, r: int, col: TableColumn):
        t = self.theme
        if col.group == "" or col.is_time:
            return QtGui.QColor(t.text_dim)
        return QtGui.QColor(t.text)

    def _tooltip(self, r: int, col: TableColumn) -> str:
        if col.channel is None:
            return f"wiersz {r + 1}"
        v = self._value(r, col)
        head = f"{col.group_title} — {col.title} [{col.unit}]" if col.unit else \
               f"{col.group_title} — {col.title}"
        body = fmt_num(v) if v is not None else "(brak danych)"
        return f"{head}\nwiersz {r + 1}: {body}"

    # ------------------------------------------------------------------- akcje
    def refresh(self):
        self.beginResetModel()
        self._build_columns()
        self.endResetModel()

    def set_heatmap(self, on: bool):
        self.heatmap = on
        self._rebuild_view()

    def set_heatmap_color(self, color: str):
        self.heatmap_color = color
        self._rebuild_view()

    def set_show_deltas(self, on: bool):
        self.show_deltas = on
        self._rebuild_view()

    def set_hover_row(self, group: str, row: Optional[int]):
        """Podświetla wiersz najbliższy kursorowi wykresu."""
        if self.hover_rows.get(group) == row:
            return
        old = self.hover_rows.get(group)
        self.hover_rows[group] = row
        for rr in (old, row):
            if rr is None or rr < 0 or rr >= self.n_rows:
                continue
            left = self.index(rr, 0)
            right = self.index(rr, self.columnCount() - 1)
            self.dataChanged.emit(left, right, [Qt.BackgroundRole])

    def row_for_time(self, group: str, t: float) -> Optional[int]:
        arr = self._group_time(group)
        if arr is None or not len(arr):
            return None
        i = int(np.searchsorted(arr, t))
        i = min(max(i, 0), len(arr) - 1)
        if i > 0 and abs(arr[i - 1] - t) <= abs(arr[i] - t):
            i -= 1
        return i


class HeatCellDelegate(QtWidgets.QStyledItemDelegate):
    """Rysuje wartość oraz kolorową strzałkę zmiany (zielona ▲ / czerwona ▼)."""

    COLOR_UP = "#2ea043"
    COLOR_DOWN = "#d64545"

    def paint(self, painter: QtGui.QPainter, option, index):
        text = index.data(Qt.DisplayRole)
        text = "" if text is None else str(text)
        arrow = ""
        if text.endswith("▲") or text.endswith("▼"):
            arrow, text = text[-1], text[:-1].rstrip()

        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        rect = option.rect.adjusted(5, 0, -6, 0)
        painter.save()
        color = index.data(Qt.ForegroundRole)
        painter.setPen(QtGui.QColor(color) if color is not None else option.palette.text().color())
        painter.drawText(rect, int(Qt.AlignRight | Qt.AlignVCenter), text)
        if arrow:
            fm = painter.fontMetrics()
            x = rect.right() - fm.horizontalAdvance(text) - 3
            painter.setPen(QtGui.QColor(self.COLOR_UP if arrow == "▲" else self.COLOR_DOWN))
            f = painter.font()
            f.setPointSizeF(max(6.5, f.pointSizeF() - 0.5))
            painter.setFont(f)
            painter.drawText(
                QtCore.QRect(x - 13, rect.top(), 13, rect.height()),
                int(Qt.AlignRight | Qt.AlignVCenter), arrow,
            )
        painter.restore()


class GroupedHeader(QtWidgets.QHeaderView):
    """Nagłówek dwupoziomowy: nazwa grupy nad nazwą parametru."""

    def __init__(self, orientation, model: LogTableModel, theme: Theme, parent=None):
        super().__init__(orientation, parent)
        self._model = model
        self.theme = theme
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setDefaultSectionSize(96)
        self.setMinimumHeight(46)

    def set_theme(self, theme: Theme):
        self.theme = theme
        self.viewport().update()

    def paintSection(self, painter: QtGui.QPainter, rect: QtCore.QRect, logicalIndex: int):  # noqa: N802
        if not rect.isValid() or logicalIndex >= len(self._model.columns):
            return
        col = self._model.columns[logicalIndex]
        t = self.theme
        painter.save()
        painter.fillRect(rect, QtGui.QColor(t.panel_alt))
        # linie siatki
        painter.setPen(QtGui.QPen(QtGui.QColor(t.border), 1))
        painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        unit = f" [{col.unit}]" if col.unit and not col.is_time else ""
        title = f"{col.title}{unit}"
        if col.group:
            gcolor = QtGui.QColor(self._model.color_of(col))
            if col.is_time:
                gcolor = QtGui.QColor(t.text_dim)
            painter.setPen(QtGui.QPen(gcolor))
            f = painter.font()
            f.setPointSizeF(8.0)
            f.setBold(False)
            painter.setFont(f)
            painter.drawText(
                rect.adjusted(6, 3, -4, 0),
                int(Qt.AlignLeft | Qt.AlignTop),
                col.group_title,
            )
        f = painter.font()
        f.setPointSizeF(8.8)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QtGui.QPen(QtGui.QColor(t.text)))
        text_rect = rect.adjusted(6, 18, -4, -2)
        metrics = QtGui.QFontMetrics(f)
        elided = metrics.elidedText(title, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, int(Qt.AlignLeft | Qt.AlignVCenter), elided)
        painter.restore()


class LogTable(QtWidgets.QWidget):
    """Widok tabeli logu z heatmapą, strzałkami zmian i śledzeniem kursora."""

    rowClicked = Signal(float)          # czas klikniętego wiersza (oś wykresu)

    def __init__(self, log: LogData, theme: Theme, parent=None):
        super().__init__(parent)
        self.log = log
        self.theme = theme
        self.model = LogTableModel(log, theme, self)

        self.view = QtWidgets.QTableView(self)
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(False)
        self.view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.view.setWordWrap(False)
        self.view.setShowGrid(False)
        self.view.verticalHeader().setDefaultSectionSize(19)
        self.view.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.view.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.view.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.header = GroupedHeader(Qt.Horizontal, self.model, theme, self.view)
        self.view.setHorizontalHeader(self.header)
        self.view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.horizontalHeader().customContextMenuRequested.connect(self._header_menu)

        self.view.clicked.connect(self._on_clicked)
        self.view.setItemDelegate(HeatCellDelegate(self.view))

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addLayout(self._toolbar())
        lay.addWidget(self.view)
        self._apply_sizes()

    def _toolbar(self) -> QtWidgets.QHBoxLayout:
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 0)
        self.chk_heat = QtWidgets.QCheckBox("Kolorowanie narastające")
        self.chk_heat.setChecked(True)
        self.chk_heat.setToolTip("Koloruje komórki wg wartości — im wyższa, tym mocniejszy kolor")
        self.chk_heat.toggled.connect(self.model.set_heatmap)

        self.chk_delta = QtWidgets.QCheckBox("Strzałki zmian")
        self.chk_delta.setChecked(True)
        self.chk_delta.setToolTip("Pokazuje wzrosty i spadki względem poprzedniego wiersza (próg 1% zakresu kolumny)")
        self.chk_delta.toggled.connect(self.model.set_show_deltas)

        legend = QtWidgets.QLabel(
            "<span style='color:#2ea043;'>▲ wzrost</span> &nbsp; "
            "<span style='color:#d64545;'>▼ spadek</span> &nbsp; względem poprzedniego wiersza"
        )
        legend.setObjectName("hint")

        self.cmb_color = QtWidgets.QComboBox()
        for name, color in (
            ("Zielona", "#12a150"),
            ("Niebieska", "#2f6fed"),
            ("Pomarańczowa", "#e8871e"),
            ("Fioletowa", "#8b5cf6"),
            ("Tęczowa (niebieski→czerwony)", "rainbow"),
        ):
            self.cmb_color.addItem(name, color)
        self.cmb_color.currentIndexChanged.connect(
            lambda: self.model.set_heatmap_color(self.cmb_color.currentData())
        )
        self.cmb_color.setToolTip("Skala kolorów heatmapy")

        bar.addWidget(self.chk_heat)
        bar.addWidget(self.cmb_color)
        bar.addWidget(self.chk_delta)
        bar.addWidget(legend)
        bar.addStretch(1)
        return bar

    def _apply_sizes(self):
        cols = self.model.columns
        for i, col in enumerate(cols):
            if col.group == "":
                self.view.setColumnWidth(i, 46)
            elif col.is_time:
                self.view.setColumnWidth(i, 78)
            else:
                self.view.setColumnWidth(i, max(92, min(150, 9 * len(col.title) + 34)))

    # ------------------------------------------------------------------- akcje
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.model.set_theme(theme)
        self.header.set_theme(theme)

    def highlight_time(self, t: float, follow: bool = True):
        """Podświetla wiersze najbliższe wskazanemu czasowi."""
        first_row = None
        for grp in self.log.groups:
            row = self.model.row_for_time(grp.letter, t)
            self.model.set_hover_row(grp.letter, row)
            if first_row is None:
                first_row = row
        if follow and first_row is not None:
            idx = self.model.index(first_row, 0)
            self.view.scrollTo(idx, QtWidgets.QAbstractItemView.EnsureVisible)

    def clear_highlight(self):
        for grp in self.log.groups:
            self.model.set_hover_row(grp.letter, None)

    def _on_clicked(self, index: QtCore.QModelIndex):
        col = self.model.columns[index.column()]
        if not col.group:
            return
        t = self.model._value(index.row(), col) if col.is_time else None
        if t is None:
            arr = self.model._group_time(col.group)
            if arr is not None and index.row() < len(arr):
                t = float(arr[index.row()])
        if t is not None:
            self.rowClicked.emit(float(t))

    def _header_menu(self, pos: QtCore.QPoint):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Pokaż wszystkie kolumny").triggered.connect(
            lambda: [self.view.setColumnHidden(i, False) for i in range(self.model.columnCount())]
        )
        menu.addSeparator()
        for i, col in enumerate(self.model.columns):
            if col.group == "":
                continue
            unit = f" [{col.unit}]" if col.unit else ""
            act = menu.addAction(f"{col.group_title} — {col.title}{unit}")
            act.setCheckable(True)
            act.setChecked(not self.view.isColumnHidden(i))
            act.triggered.connect(lambda checked, idx=i: self.view.setColumnHidden(idx, not checked))
        menu.exec(self.header.mapToGlobal(pos))
