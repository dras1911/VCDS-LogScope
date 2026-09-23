"""Widok pojedynczego logu: wykres nakładany, panel serii i tabela."""

from __future__ import annotations

from typing import Optional

import numpy as np
from .qt import QAction, Qt, QtCore, QtGui, QtWidgets, Signal

from .bandview import BandsChart
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
        self._cursor_time: Optional[float] = None   # czas kursora, gdy ustawia go tabela

        self.chart = LogChart(theme, self)
        self.bands = BandsChart(theme, self)
        self.view_stack = QtWidgets.QStackedWidget(self)
        self.view_stack.addWidget(self.chart)
        self.view_stack.addWidget(self.bands)
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
        cbl.addWidget(self.lbl_hint)
        cbl.addWidget(self.view_stack, 1)

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
        self.bands.cursorMoved.connect(self._on_cursor)
        self.bands.doubleClicked.connect(self.bands.fit)
        self.bands.set_secondary_fn(self._secondary_text)
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

        lay.addWidget(QtWidgets.QLabel("Widok:"))
        self.cmb_view = QtWidgets.QComboBox()
        self.cmb_view.addItem("Nakładany", "overlay")
        self.cmb_view.addItem("Pasma", "bands")
        self.cmb_view.setFixedWidth(130)
        self.cmb_view.setToolTip(
            "Nakładany — wszystkie serie na jednym wykresie (jak w TuneZilla).\n"
            "Pasma — każdy parametr w osobnym pasie z własną skalą i wspólnym kursorem.\n"
            "Przy 6+ parametrach pasma są znacznie czytelniejsze."
        )
        self.cmb_view.currentIndexChanged.connect(self._on_view_mode)
        lay.addWidget(self.cmb_view)

        lay.addWidget(QtWidgets.QLabel("Oś X:"))
        self.cmb_x = QtWidgets.QComboBox()
        self.cmb_x.addItem("Czas [s]", X_TIME)
        self.cmb_x.addItem("Obroty [obr/min]", X_RPM)
        self.cmb_x.setFixedWidth(160)
        self.cmb_x.currentIndexChanged.connect(self._on_x_mode)
        lay.addWidget(self.cmb_x)

        self.chk_sweeps = QtWidgets.QCheckBox("Dziel na przebiegi")
        self.chk_sweeps.setChecked(True)
        self.chk_sweeps.setToolTip(
            "Przy osi obrotów: dzieli dane w miejscach, gdzie obroty zawracają (np. koniec\n"
            "przyspieszania) i rysuje każdy przebieg osobno, sortując próbki po obrotach.\n"
            "Bez tego linia wraca po tych samych obrotach i tworzy pętle."
        )
        self.chk_sweeps.toggled.connect(lambda _checked=False: self.rebuild_series())
        self.chk_sweeps.setEnabled(self.x_mode == X_RPM)
        lay.addWidget(self.chk_sweeps)

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
        self.lbl_hint.setWordWrap(False)
        self.lbl_hint.setVisible(False)

        self.chk_snap = QtWidgets.QCheckBox("Przyciągaj do próbek")
        self.chk_snap.setChecked(True)
        self.chk_snap.toggled.connect(self.chart.set_snap)
        self.chk_snap.toggled.connect(self.bands.set_snap)
        lay.addWidget(self.chk_snap)

        self.chk_follow = QtWidgets.QCheckBox("Tabela podąża za kursorem")
        self.chk_follow.setChecked(True)
        self.chk_follow.setToolTip(
            "Przewijanie tabeli razem z kursorem wykresu.\n"
            "Przy osi czasu działa liniowo. Przy osi obrotów kursor przeskakuje między\n"
            "przebiegami (wiele próbek ma te same obroty), więc tabela może się cofać."
        )
        self.chk_follow.toggled.connect(lambda v: setattr(self, "_follow_table", v))
        lay.addWidget(self.chk_follow)

        lay.addStretch(1)

        for text, tip, slot in (
            ("Dopasuj", "Dopasuj widok do całego logu (dwuklik na wykresie)", self._fit_active),
            ("−", "Pomniejsz", lambda: self._zoom_active(1.25)),
            ("+", "Powiększ", lambda: self._zoom_active(0.8)),
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
        split = self.x_mode == X_RPM and self.chk_sweeps.isChecked()
        for ch in self.log.channels:
            if not ch.has_data:
                continue
            x, y = self.log.plot_xy(ch, self.x_mode, split_sweeps=split)
            specs.append(
                SeriesSpec(
                    sid=sid_for(ch),
                    label=ch.label,
                    short=ch.short_label,
                    unit=ch.unit,
                    color=self.colors.get(ch.match_key, "#9aa0a6"),
                    x=x,
                    y=y,
                    group=ch.group,
                    lookup_x=self.log.x_for(ch, self.x_mode),
                    lookup_y=ch.y,
                )
            )
        self.chart.set_x_axis(
            self.x_mode,
            "obr/min" if self.x_mode == X_RPM else "s",
            "Obroty silnika" if self.x_mode == X_RPM else "Czas",
        )
        self.chart.set_series(specs)
        self.bands.set_x_axis(
            self.x_mode,
            "obr/min" if self.x_mode == X_RPM else "s",
            "Obroty silnika" if self.x_mode == X_RPM else "Czas",
        )
        self.bands.set_series(specs)
        if self.chart.cursor_x() is not None:
            self.bands.set_cursor_x(self.chart.cursor_x(), emit=False)
        self._sync_panel_checks()
        self._check_scales()

    def _sync_panel_checks(self):
        for i in range(self.panel.list.count()):
            item = self.panel.list.item(i)
            sid = item.data(Qt.UserRole)
            if sid:
                visible = item.checkState() == Qt.Checked
                self.chart.set_series_visible(str(sid), visible)
                self.bands.set_series_visible(str(sid), visible)

    def _on_view_mode(self):
        """Przełączenie widoku: nakładany <-> pasma."""
        bands = self.cmb_view.currentData() == "bands"
        self.view_stack.setCurrentWidget(self.bands if bands else self.chart)
        self.chk_norm.setEnabled(not bands)
        self.chk_norm.setToolTip(
            "W widoku pasm każdy parametr ma własną skalę, więc normalizacja nie jest potrzebna."
            if bands else
            "Przeskalowuje każdą serię do jej własnego zakresu (0–100%).\n"
            "Dzięki temu widać kształty wszystkich parametrów, mimo że obroty mają\n"
            "zakres 0–6000, a np. temperatura 80–90. Wartości w dymku pozostają rzeczywiste."
        )
        if self.chart.cursor_x() is not None:
            self.bands.set_cursor_x(self.chart.cursor_x(), emit=False)
        self.bands.fit() if bands else self.chart.fit()
        self._check_scales()

    def _active_view(self):
        return self.bands if self.cmb_view.currentData() == "bands" else self.chart

    def _fit_active(self):
        self._active_view().fit()

    def _zoom_active(self, factor: float):
        self._active_view().zoom(factor)

    def _export_active(self):
        view = self._active_view()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Zapisz wykres jako PNG", "wykres.png", "Obraz PNG (*.png)"
        )
        if path:
            if not view.export_png(path):
                QtWidgets.QMessageBox.warning(self, "Eksport", "Nie udało się zapisać obrazu.")

    def _on_normalize(self, on: bool):
        self.chart.set_normalized(on)
        self._check_scales()

    def _check_scales(self):
        """Podpowiedzi kontekstowe: normalizacja przy różnych zakresach, przebiegi przy osi obrotów."""
        if self.x_mode == X_RPM:
            segments = self.log.rpm_segments()
            if len(segments) > 1:
                text = (f"Oś X = obroty: linie podzielone na {len(segments)} przebiegi i posortowane "
                        "po obrotach (bez pętli). Obroty są osią, nie serią. Wiersz tabeli odpowiada "
                        "jednej wartości obrotów, więc kursor może przeskakiwać między przebiegami.")
            else:
                text = "Oś X = obroty (obroty są osią, nie serią)."
            self._set_hint(text)
            return
        spans = []
        for ch in self.log.numeric_channels:
            if ch.has_data:
                lo, hi, _ = ch.stats()
                spans.append(hi - lo)
        if not spans or self.chk_norm.isChecked():
            self._set_hint("")
            return
        spans.sort()
        ratio = spans[-1] / max(spans[0], 1e-9)
        if self.cmb_view.currentData() == "bands":
            self._set_hint("")
            return
        visible = sum(1 for i in range(self.panel.list.count())
                      if self.panel.list.item(i).checkState() == Qt.Checked)
        if visible >= 6 and ratio > 25:
            self._set_hint(
                f"Widok nakładany z {visible} seriami o bardzo różnych zakresach bywa nieczytelny — "
                "przełącz „Widok: Pasma” albo włącz „Normalizuj 0–100%”."
            )
            return
        self._set_hint(
            "Wskazówka: zakresy parametrów różnią się bardzo — włącz „Normalizuj 0–100%”, "
            "aby widzieć kształt każdej serii"
            if ratio > 25 else ""
        )

    def _set_hint(self, text: str):
        self.lbl_hint.setText(text)
        self.lbl_hint.setVisible(bool(text))

    def _on_series_toggled(self, sid: str, checked: bool):
        self.chart.set_series_visible(sid, checked)
        self.bands.set_series_visible(sid, checked)

    def _on_x_mode(self):
        self.x_mode = self.cmb_x.currentData()
        if self.x_mode == X_RPM:
            # obroty są teraz osią X — nie rysujemy ich jako serii (byłaby to linia y = x)
            self._set_rpm_visible(False)
        else:
            self._set_rpm_visible(True)
        self.chk_sweeps.setEnabled(self.x_mode == X_RPM)
        self.rebuild_series()

    def _set_rpm_visible(self, visible: bool):
        """Włącza/wyłącza kanały obrotów w panelu (przy osi X = obroty są zbędne)."""
        for ch in self.log.channels:
            if not ch.is_rpm or not ch.has_data:
                continue
            sid = sid_for(ch)
            for i in range(self.panel.list.count()):
                item = self.panel.list.item(i)
                if item.data(Qt.UserRole) == sid:
                    item.setCheckState(Qt.Checked if visible else Qt.Unchecked)

    def _export_png(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Zapisz wykres jako PNG",
            f"{self.log.meta.file_name or 'wykres'}.png", "Obraz PNG (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        ok = self._active_view().export_png(path)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Zapisano" if ok else "Nie udało się zapisać")

    # ------------------------------------------------------------- synchronizacja
    def _on_cursor(self, x: float):
        # kursor jest wspólny dla obu widoków — przełączenie nie gubi pozycji
        source = self.sender()
        target = self.bands if source is self.chart else self.chart
        try:
            target.set_cursor_x(x, emit=False, snap=False)
        except TypeError:
            target.set_cursor_x(x, emit=False)
        t = self._cursor_time if self._cursor_time is not None else (
            x if self.x_mode == X_TIME else self._time_for_rpm(x))
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
        """Ustawia kursor wg czasu (np. po kliknięciu wiersza tabeli).

        Przy osi obrotów czas jest znany dokładnie, więc zapamiętujemy go na czas ustawiania
        kursora — inaczej odczyt z osi obrotów (wiele próbek ma te same obroty) cofałby
        podświetlenie tabeli na wiersz o tych samych obrotach, ale z innego przebiegu.
        """
        self._cursor_time = float(t)
        try:
            if self.x_mode == X_TIME:
                x = float(t)
            else:
                rpm = self.log.rpm_at(t)
                if rpm is None:
                    return
                x = float(rpm)
            self.chart.set_cursor_x(x, snap=True)
            self._active_view().ensure_visible(self.chart.cursor_x() or x)
        finally:
            self._cursor_time = None

    def _on_row_clicked(self, t: float):
        """Klik w wiersz tabeli ustawia kursor wykresu."""
        self.set_cursor_time(t)
        self.table.highlight_time(t, follow=False)

    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.colors = color_map(self.log.channels, theme.is_dark)
        self.chart.refresh_theme(theme)
        self.bands.refresh_theme(theme)
        self.table.set_theme(theme)
        self.panel.theme = theme
        self.panel.populate(self.log, self.colors)
        self.rebuild_series()
        self._sync_panel_checks()

    # ---------------------------------------------------------------- widoczność
    def set_table_visible(self, on: bool):
        self.table.setVisible(on)

    def set_chart_visible(self, on: bool):
        self.view_stack.setVisible(on)      # chowamy oba widoki (nakładany i pasma) razem
