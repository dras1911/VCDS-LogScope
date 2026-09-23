"""Widok pojedynczego logu: wykres nakładany, panel serii i tabela."""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

from .chartview import LogChart, SeriesSpec
from .colors import color_map
from .formatting import fmt_num, fmt_time
from .model import X_RPM, X_TIME, Channel, LogData
from .tableview import LogTable
from .theme import Theme


def sid_for(channel: Channel) -> str:
    name, unit, occ = channel.match_key
    return f"{name}|{unit}|{occ}"


class SeriesPanel(QtWidgets.QWidget):
    """Lista serii z kolorami, zakresami i przełącznikami widoczności."""

    toggled = Signal(str, bool)

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.list = QtWidgets.QListWidget(self)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.list.setUniformItemSizes(True)
        self.list.setIconSize(QtCore.QSize(12, 12))
        self.list.itemChanged.connect(self._on_item_changed)

        head = QtWidgets.QLabel("Parametry")
        head.setStyleSheet("font-weight:600; padding:2px 4px;")
        btn_all = QtWidgets.QPushButton("Wszystkie")
        btn_none = QtWidgets.QPushButton("Żadne")
        btn_rpm = QtWidgets.QPushButton("Tylko obroty")
        for b in (btn_all, btn_none, btn_rpm):
            b.setFixedHeight(24)
        btn_all.clicked.connect(lambda: self.set_all(True))
        btn_none.clicked.connect(lambda: self.set_all(False))
        btn_rpm.clicked.connect(self.only_rpm)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        row.addWidget(btn_rpm)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 4, 4)
        lay.setSpacing(4)
        lay.addWidget(head)
        lay.addLayout(row)
        lay.addWidget(self.list, 1)

    # ------------------------------------------------------------------ budowa
    def populate(self, log: LogData, colors: dict | None = None):
        colors = colors if colors is not None else color_map(log.channels, self.theme.is_dark)
        self.list.blockSignals(True)
        self.list.clear()
        for grp in log.groups:
            header = QtWidgets.QListWidgetItem(f"Grupa {grp.letter}: {grp.group_id}")
            header.setFlags(Qt.NoItemFlags)
            f = header.font()
            f.setBold(True)
            f.setPointSizeF(8.2)
            header.setFont(f)
            header.setForeground(QtGui.QColor(self.theme.text_dim))
            self.list.addItem(header)
            for ch in grp.channels:
                if not ch.has_data:
                    continue
                item = QtWidgets.QListWidgetItem(f"{ch.display_name}  {ch.unit_label}".strip())
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, sid_for(ch))
                lo, hi, _ = ch.stats()
                item.setToolTip(
                    f"{ch.display_name} [{ch.unit}]\nzakres: {fmt_num(lo)} … {fmt_num(hi)}\n"
                    f"próbek: {len(ch.t)}"
                )
                item.setIcon(self._swatch(colors.get(ch.match_key, "#9aa0a6")))
                self.list.addItem(item)
        self.list.blockSignals(False)

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

    # ------------------------------------------------------------------- akcje
    def _on_item_changed(self, item: QtWidgets.QListWidgetItem):
        sid = item.data(Qt.UserRole)
        if sid:
            self.toggled.emit(str(sid), item.checkState() == Qt.Checked)

    def set_all(self, checked: bool):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.UserRole):
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list.blockSignals(False)
        for i in range(self.list.count()):
            item = self.list.item(i)
            sid = item.data(Qt.UserRole)
            if sid:
                self.toggled.emit(str(sid), checked)

    def only_rpm(self):
        self.list.blockSignals(True)
        states = {}
        for i in range(self.list.count()):
            item = self.list.item(i)
            sid = item.data(Qt.UserRole)
            if not sid:
                continue
            is_rpm = "obroty" in sid or "engine speed" in sid or "rpm" in sid
            item.setCheckState(Qt.Checked if is_rpm else Qt.Unchecked)
            states[str(sid)] = is_rpm
        self.list.blockSignals(False)
        for sid, state in states.items():
            self.toggled.emit(sid, state)


class LogView(QtWidgets.QWidget):
    """Kompletny widok jednego logu: wykres + tabela + panel parametrów."""

    cursorMoved = Signal(float, float, object)   # czas, wartość RPM (lub nan), log

    def __init__(self, log: LogData, theme: Theme, parent=None):
        super().__init__(parent)
        self.log = log
        self.theme = theme
        self.x_mode = X_TIME
        self._follow_table = True

        self.chart = LogChart(theme, self)
        self.table = LogTable(log, theme, self)
        self.panel = SeriesPanel(theme, self)
        self.colors = color_map(log.channels, theme.is_dark)
        self.panel.populate(log, self.colors)

        self._build_toolbar()

        chart_box = QtWidgets.QWidget(self)
        cbl = QtWidgets.QVBoxLayout(chart_box)
        cbl.setContentsMargins(0, 0, 0, 0)
        cbl.setSpacing(4)
        cbl.addWidget(self.chart_toolbar)
        cbl.addWidget(self.chart, 1)

        self.splitter = QtWidgets.QSplitter(Qt.Vertical, self)
        self.splitter.addWidget(chart_box)
        self.splitter.addWidget(self.table)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([620, 380])

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.panel.setFixedWidth(268)
        body.addWidget(self.panel)
        body.addWidget(self.splitter, 1)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addLayout(body)

        self.chart.cursorMoved.connect(self._on_cursor)
        self.table.rowClicked.connect(self._on_row_clicked)
        self.panel.toggled.connect(self._on_series_toggled)
        self.chart.doubleClicked.connect(self.chart.fit)
        self.chart.set_secondary_fn(self._secondary_text)

        self.rebuild_series()

    # ---------------------------------------------------------------- toolbar
    def _build_toolbar(self):
        tb = QtWidgets.QWidget(self)
        lay = QtWidgets.QHBoxLayout(tb)
        lay.setContentsMargins(4, 2, 4, 0)
        lay.setSpacing(8)

        lay.addWidget(QtWidgets.QLabel("Oś X:"))
        self.cmb_x = QtWidgets.QComboBox()
        self.cmb_x.addItem("Czas [s]", X_TIME)
        self.cmb_x.addItem("Obroty [obr/min]", X_RPM)
        self.cmb_x.setFixedWidth(160)
        self.cmb_x.currentIndexChanged.connect(self._on_x_mode)
        lay.addWidget(self.cmb_x)

        self.chk_norm = QtWidgets.QCheckBox("Normalizuj 0–100%")
        self.chk_norm.setToolTip(
            "Przeskalowuje każdą serię do jej własnego zakresu (0–100%).\n"
            "Dzięki temu widać kształty wszystkich parametrów, mimo że obroty mają\n"
            "zakres 0–6000, a np. temperatura 80–90. Wartości w dymku pozostają rzeczywiste."
        )
        self.chk_norm.toggled.connect(self._on_normalize)
        lay.addWidget(self.chk_norm)

        self.lbl_hint = QtWidgets.QLabel("")
        self.lbl_hint.setObjectName("hint")
        self.lbl_hint.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        lay.addWidget(self.lbl_hint)

        self.chk_snap = QtWidgets.QCheckBox("Przyciągaj do próbek")
        self.chk_snap.setChecked(True)
        self.chk_snap.toggled.connect(self.chart.set_snap)
        lay.addWidget(self.chk_snap)

        self.chk_follow = QtWidgets.QCheckBox("Tabela podąża za kursorem")
        self.chk_follow.setChecked(True)
        self.chk_follow.toggled.connect(lambda v: setattr(self, "_follow_table", v))
        lay.addWidget(self.chk_follow)

        lay.addStretch(1)

        for text, tip, slot in (
            ("Dopasuj", "Dopasuj widok do całego logu (dwuklik na wykresie)", self.chart.fit),
            ("−", "Pomniejsz", lambda: self.chart.zoom(1.25)),
            ("+", "Powiększ", lambda: self.chart.zoom(0.8)),
            ("PNG", "Zapisz wykres jako obraz PNG", self._export_png),
        ):
            b = QtWidgets.QPushButton(text)
            b.setToolTip(tip)
            b.setFixedHeight(26)
            b.clicked.connect(slot)
            lay.addWidget(b)

        self.chart_toolbar = tb

    # ------------------------------------------------------------------ serie
    def rebuild_series(self):
        specs: list[SeriesSpec] = []
        for ch in self.log.channels:
            if not ch.has_data:
                continue
            specs.append(
                SeriesSpec(
                    sid=sid_for(ch),
                    label=ch.label,
                    short=ch.short_label,
                    unit=ch.unit,
                    color=self.colors.get(ch.match_key, "#9aa0a6"),
                    x=self.log.x_for(ch, self.x_mode),
                    y=ch.y,
                    group=ch.group,
                )
            )
        self.chart.set_x_axis(
            self.x_mode,
            "obr/min" if self.x_mode == X_RPM else "s",
            "Obroty silnika" if self.x_mode == X_RPM else "Czas",
        )
        self.chart.set_series(specs)
        self._sync_panel_checks()
        self._check_scales()

    def _sync_panel_checks(self):
        for i in range(self.panel.list.count()):
            item = self.panel.list.item(i)
            sid = item.data(Qt.UserRole)
            if sid:
                self.chart.set_series_visible(str(sid), item.checkState() == Qt.Checked)

    def _on_normalize(self, on: bool):
        self.chart.set_normalized(on)
        self._check_scales()

    def _check_scales(self):
        """Podpowiada normalizację, gdy rozpiętości parametrów bardzo się różnią."""
        spans = []
        for ch in self.log.numeric_channels:
            if ch.has_data:
                lo, hi, _ = ch.stats()
                spans.append(hi - lo)
        if not spans or self.chk_norm.isChecked():
            self.lbl_hint.setText("")
            return
        spans.sort()
        ratio = spans[-1] / max(spans[0], 1e-9)
        if ratio > 25:
            self.lbl_hint.setText(
                "Wskazówka: zakresy parametrów różnią się bardzo — włącz „Normalizuj 0–100%”, "
                "aby widzieć kształt każdej serii"
            )
        else:
            self.lbl_hint.setText("")

    def _on_series_toggled(self, sid: str, checked: bool):
        self.chart.set_series_visible(sid, checked)

    def _on_x_mode(self):
        self.x_mode = self.cmb_x.currentData()
        self.rebuild_series()

    def _export_png(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Zapisz wykres jako PNG",
            f"{self.log.meta.file_name or 'wykres'}.png", "Obraz PNG (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        ok = self.chart.export_png(path)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Zapisano" if ok else "Nie udało się zapisać")

    # ------------------------------------------------------------- synchronizacja
    def _on_cursor(self, x: float):
        t = x if self.x_mode == X_TIME else self._time_for_rpm(x)
        rpm = self.log.rpm_nearest(t) if t is not None else None
        if t is not None:
            self.table.highlight_time(t, follow=self._follow_table)
        self.cursorMoved.emit(float(t if t is not None else x), float(rpm) if rpm is not None else float("nan"), self)

    def _time_for_rpm(self, rpm: float) -> Optional[float]:
        """Zamienia pozycję na osi RPM na czas (dla tabeli i statusu)."""
        series = self.log.rpm_series()
        if series is None:
            return None
        rt, ry = series
        order = np.argsort(ry)
        return float(np.interp(rpm, ry[order], rt[order]))

    def _secondary_text(self, x: float) -> str:
        """Dodatkowy opis przy etykiecie kursora: obroty (dla osi czasu) lub czas (dla osi RPM)."""
        if self.x_mode == X_TIME:
            rpm = self.log.rpm_nearest(x)
            return f"{fmt_num(rpm)} obr/min" if rpm is not None else ""
        t = self._time_for_rpm(x)
        return f"{fmt_num(t, 2)} s" if t is not None else ""

    def set_cursor_time(self, t: float):
        """Ustawia kursor wg czasu (np. po kliknięciu wiersza tabeli)."""
        if self.x_mode == X_TIME:
            self.chart.set_cursor_x(t, snap=True)
        else:
            rpm = self.log.rpm_at(t)
            if rpm is not None:
                self.chart.set_cursor_x(rpm, snap=True)

    def _on_row_clicked(self, t: float):
        """Klik w wiersz tabeli ustawia kursor wykresu."""
        self.set_cursor_time(t)
        self.table.highlight_time(t, follow=False)

    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.colors = color_map(self.log.channels, theme.is_dark)
        self.chart.refresh_theme(theme)
        self.table.set_theme(theme)
        self.panel.theme = theme
        self.panel.populate(self.log, self.colors)
        self.rebuild_series()
        self._sync_panel_checks()

    # ---------------------------------------------------------------- widoczność
    def set_table_visible(self, on: bool):
        self.table.setVisible(on)

    def set_chart_visible(self, on: bool):
        self.chart.setVisible(on)
