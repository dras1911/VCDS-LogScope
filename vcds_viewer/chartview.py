"""Wykres nakładany: wiele serii razem, linia kursora i dymek z wartościami."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pyqtgraph as pg
from .qt import QAction, Qt, QtCore, QtGui, QtWidgets, Signal

from .colors import hex_to_rgba
from .formatting import fmt_num
from .theme import Theme


@dataclass
class SeriesSpec:
    """Pojedyncza seria do narysowania na wykresie."""

    sid: str                       # unikalny identyfikator
    label: str                     # pełna etykieta (z grupą i jednostką)
    short: str                     # krótka etykieta (bez grupy)
    unit: str
    color: str
    x: np.ndarray                  # wartości osi X do rysowania
    y: np.ndarray                  # wartości do rysowania
    style: int = Qt.SolidLine
    width: float = 1.7
    mode: str = "line"             # "line" | "points" | "mean" (średnia po obrotach)
    tag: str = ""                  # np. "Log A" / "Log B" (tryb porównania)
    group: str = ""
    lookup_x: Optional[np.ndarray] = None   # wartości do odczytu pod kursorem (kolejność czasu)
    lookup_y: Optional[np.ndarray] = None


class _Series:
    __slots__ = ("spec", "curve", "dots", "visible", "px", "py", "lx", "ly", "ymin", "ymax")

    def __init__(self, spec: SeriesSpec):
        self.spec = spec
        self.curve: Optional[pg.PlotDataItem] = None
        self.dots: Optional[pg.ScatterPlotItem] = None
        self.visible = True
        self.px = np.asarray(spec.x, dtype=float)
        self.py = np.asarray(spec.y, dtype=float)
        # tablice do odczytu wartości pod kursorem (bez przerw na przebiegi)
        self.lx = np.asarray(spec.lookup_x, dtype=float) if spec.lookup_x is not None else self.px
        self.ly = np.asarray(spec.lookup_y, dtype=float) if spec.lookup_y is not None else self.py
        finite = self.ly[np.isfinite(self.ly)]
        self.ymin = float(finite.min()) if len(finite) else 0.0
        self.ymax = float(finite.max()) if len(finite) else 1.0


class LogViewBox(pg.ViewBox):
    """ViewBox z zoomem tylko po X (kółko myszy) i Ctrl+rolka = zoom po Y."""

    def wheelEvent(self, ev, axis=None):  # noqa: N802 (API pyqtgraph)
        if ev.modifiers() & Qt.ControlModifier:
            super().wheelEvent(ev, axis=1)
            return
        delta = ev.delta() or 0
        if delta == 0:
            return
        scale = 0.85 if delta > 0 else 1.0 / 0.85
        center = self.mapSceneToView(ev.scenePos())
        self.scaleBy((scale, 1.0), center=QtCore.QPointF(center.x(), center.y()))
        ev.accept()


class LogChart(QtWidgets.QWidget):
    """Nakładany wykres wielu serii z kursorem pomiarowym i dymkiem wartości."""

    cursorMoved = Signal(float)      # pozycja kursora na osi X
    pinChanged = Signal(bool)        # czy kursor jest przypięty
    doubleClicked = Signal()

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._series: dict[str, _Series] = {}
        self._order: list[str] = []
        self._normalized = False
        self._snap = True
        self._pinned = False
        self._cursor_x: Optional[float] = None
        self._x_mode = "time"
        self._x_unit = "s"
        self._user_zoomed = False

        pg.setConfigOptions(antialias=True, background=theme.plot_bg, foreground=theme.text_dim)

        self.pw = pg.PlotWidget(viewBox=LogViewBox(enableMenu=False), background=theme.plot_bg)
        self.pw.setMenuEnabled(False)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.pw)

        self.plot = self.pw.getPlotItem()
        self.vb = self.plot.vb
        self.plot.setMenuEnabled(False)
        self.plot.showGrid(x=True, y=True, alpha=0.16)
        self.plot.showAxis("right")
        self.plot.getAxis("right").setStyle(showValues=True)
        self.plot.getAxis("left").setStyle(showValues=True)
        self.plot.getAxis("right").setPen(pg.mkPen(theme.border))
        self.plot.getAxis("left").setPen(pg.mkPen(theme.border))
        self.plot.getAxis("bottom").setPen(pg.mkPen(theme.border))
        self.plot.getAxis("right").setTextPen(pg.mkPen(theme.text_dim))
        self.plot.getAxis("left").setTextPen(pg.mkPen(theme.text_dim))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen(theme.text_dim))
        self.plot.getAxis("bottom").setLabel("Czas", units="s")
        self.plot.getAxis("left").setLabel("Wartość")

        # linia kursora + podpisy
        self.vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen(theme.cursor, width=1.1, style=Qt.DashLine),
        )
        self.vline.setZValue(50)
        self.plot.addItem(self.vline, ignoreBounds=True)
        self.vline.hide()

        self.marker_label = pg.TextItem(color=theme.text_dim, anchor=(0.5, 0.0))
        self.marker_label.setZValue(60)
        self.plot.addItem(self.marker_label, ignoreBounds=True)
        self.marker_label.hide()

        # etykieta przy linii kursora: dokładny czas / obroty w miejscu kursora
        self.axis_badge = QtWidgets.QLabel(self.pw)
        self.axis_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.axis_badge.setTextFormat(Qt.RichText)
        self.axis_badge.setStyleSheet(
            f"background:{theme.accent}; color:{theme.accent_text}; border-radius:6px;"
            "padding:3px 9px; font-weight:600;"
        )
        self.axis_badge.hide()
        self._secondary_fn = None

        # dymek z wartościami (zwykły widget Qt nakładany na wykres)
        self.tooltip = QtWidgets.QLabel(self.pw)
        self.tooltip.setTextFormat(Qt.RichText)
        self.tooltip.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.tooltip.setStyleSheet(
            f"background:{theme.tooltip_bg}; border:1px solid {theme.tooltip_border};"
            "border-radius:7px; padding:7px 9px; color:#e8eaed;"
        )
        self.tooltip.hide()

        self._crosshair_h = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen(theme.grid, width=1, style=Qt.DotLine)
        )
        self._crosshair_h.setZValue(40)
        self.plot.addItem(self._crosshair_h, ignoreBounds=True)
        self._crosshair_h.hide()

        self.plot.vb.sigRangeChanged.connect(self._on_range_changed)
        self.plot.vb.sigRangeChangedManually.connect(self._on_manual_range)
        self.pw.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.pw.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        self.pw.installEventFilter(self)

    # ------------------------------------------------------------------ API
    def set_secondary_fn(self, fn):
        """Funkcja zwracająca dodatkowy opis przy etykiecie kursora (np. obroty dla osi czasu)."""
        self._secondary_fn = fn

    def set_x_axis(self, mode: str, unit: str, label: str):
        self._x_mode, self._x_unit = mode, unit
        self.plot.getAxis("bottom").setLabel(label, units=unit)

    def clear(self):
        for s in self._series.values():
            if s.curve is not None:
                self.plot.removeItem(s.curve)
            if s.dots is not None:
                self.plot.removeItem(s.dots)
        self._series.clear()
        self._order.clear()
        self._cursor_x = None
        self.tooltip.hide()
        self.vline.hide()
        self.marker_label.hide()
        self.axis_badge.hide()
        self._crosshair_h.hide()

    def set_series(self, specs: list[SeriesSpec]):
        self.clear()
        for spec in specs:
            self._add_series(spec)
        self._apply_visibility()
        self.fit()

    def _add_series(self, spec: SeriesSpec):
        s = _Series(spec)
        color = spec.color
        pen = pg.mkPen(color, width=spec.width, style=spec.style)
        if spec.mode == "points":
            # Tryb punktowy: przy osi obrotów ta sama wartość obrotów wypada w kilku momentach
            # o różnych pozostałych parametrach, więc linia łączyłaby odległe w czasie próbki
            # i tworzyła zygzaki. Punkty pokazują rzeczywisty rozrzut.
            s.curve = pg.PlotDataItem(
                pen=None, symbol="o", symbolSize=5.0,
                symbolBrush=pg.mkBrush(pg.mkColor(color).red(), pg.mkColor(color).green(),
                                       pg.mkColor(color).blue(), 190),
                symbolPen=None, antialias=True,
            )
        elif spec.mode == "mean":
            # średnia po przedziałach obrotów — grubsza linia, żeby odróżnić od surowych próbek
            s.curve = pg.PlotDataItem(
                pen=pg.mkPen(color, width=spec.width + 1.0, style=spec.style),
                antialias=True, connect="finite",
            )
        else:
            s.curve = pg.PlotDataItem(pen=pen, antialias=True, connect="finite")
        # UWAGA: kolejność ma znaczenie — najpierw dodajemy krzywą do wykresu,
        # dopiero potem włączamy clipToView (inaczej pyqtgraph cache'uje zły ViewBox).
        s.curve.setZValue(10)
        self.plot.addItem(s.curve)
        if spec.mode != "points":
            s.curve.setClipToView(True)
            s.curve.setDownsampling(auto=True, method="peak")
        s.curve.setData(s.px, self._plotted_y(s))
        s.dots = pg.ScatterPlotItem(
            size=9, pen=pg.mkPen(color, width=2), brush=pg.mkBrush(color),
        )
        s.dots.setZValue(30)
        s.dots.hide()
        self.plot.addItem(s.dots)
        self._series[spec.sid] = s
        self._order.append(spec.sid)

    def set_series_visible(self, sid: str, visible: bool):
        s = self._series.get(sid)
        if s is None:
            return
        s.visible = visible
        self._apply_visibility()
        # jeśli użytkownik nie ustawił własnego zoomu, dopasuj skalę do widocznych serii
        if not self._user_zoomed:
            self.fit()
        if self._cursor_x is not None:
            self._refresh_cursor_items()

    def _apply_visibility(self):
        for s in self._series.values():
            if s.curve is not None:
                s.curve.setVisible(s.visible)
            if s.dots is not None:
                s.dots.setVisible(s.visible and self._cursor_x is not None)

    def visible_series(self) -> list[_Series]:
        return [self._series[sid] for sid in self._order
                if sid in self._series and self._series[sid].visible]

    def set_normalized(self, on: bool):
        self._normalized = on
        self.plot.getAxis("left").setLabel("% zakresu" if on else "Wartość")
        self._redraw_data()
        self.fit()

    def normalized(self) -> bool:
        return self._normalized

    def _redraw_data(self):
        for s in self._series.values():
            if s.curve is None:
                continue
            s.curve.setData(s.px, self._plotted_y(s))

    def _plotted_y(self, s: _Series) -> np.ndarray:
        if not self._normalized:
            return s.py
        span = s.ymax - s.ymin
        if span <= 0:
            return np.zeros_like(s.py)
        return (s.py - s.ymin) / span * 100.0

    def set_snap(self, on: bool):
        self._snap = on

    def ensure_visible(self, x: float, margin: float = 0.08):
        """Przesuwa widok w poziomie (bez zmiany przybliżenia), żeby x był widoczny.

        Potrzebne, gdy kursor ustawia tabela: przy osi obrotów wiersz tabeli może wypaść
        poza aktualnie oglądany zakres i kursor zniknąłby z ekranu.
        """
        lo, hi = self.plot.vb.viewRange()[0]
        span = hi - lo
        if span <= 0:
            return
        pad = span * margin
        if lo + pad <= x <= hi - pad:
            return
        if x < lo + pad:
            self.plot.vb.setXRange(x - pad, x - pad + span, padding=0.0)
        else:
            self.plot.vb.setXRange(x + pad - span, x + pad, padding=0.0)

    def fit(self):
        """Dopasowuje widok do widocznych danych."""
        self._user_zoomed = False
        vis = self.visible_series()
        if not vis:
            return
        xs = [s.px[np.isfinite(s.px)] for s in vis]
        xs = [a for a in xs if len(a)]
        ys = [self._plotted_y(s) for s in vis]
        ys = [a[np.isfinite(a)] for a in ys if len(a)]
        if not xs or not ys:
            return
        xmin = min(float(a.min()) for a in xs)
        xmax = max(float(a.max()) for a in xs)
        ymin = min(float(a.min()) for a in ys)
        ymax = max(float(a.max()) for a in ys)
        if xmax <= xmin:
            xmax = xmin + 1
        if ymax <= ymin:
            ymax = ymin + 1
        pad_y = (ymax - ymin) * 0.08
        self.plot.vb.setXRange(xmin, xmax, padding=0.01)
        self.plot.vb.setYRange(ymin - pad_y, ymax + pad_y, padding=0.0)

    def zoom(self, factor: float):
        center = self.plot.vb.viewRange()
        cx = (center[0][0] + center[0][1]) / 2
        self.plot.vb.scaleBy((factor, 1.0), center=QtCore.QPointF(cx, 0))

    # -------------------------------------------------------------- kursor
    def cursor_x(self) -> Optional[float]:
        return self._cursor_x

    def set_cursor_x(self, x: float, emit: bool = True, snap: bool = True):
        x = float(x)
        if snap and self._snap:
            x = self._snap_x(x)
        self._cursor_x = x
        self._refresh_cursor_items()
        if emit:
            self.cursorMoved.emit(x)

    def step_cursor(self, direction: int):
        """Przesuwa kursor o jedną próbkę (klawiatura ←/→)."""
        vis = [s for s in self.visible_series() if len(s.lx)]
        if not vis:
            return
        ref = np.unique(np.concatenate([s.lx[np.isfinite(s.lx)] for s in vis]))
        if not len(ref):
            return
        if self._cursor_x is None:
            self.set_cursor_x(float(ref[0]))
            self.ensure_visible(self._cursor_x)
            return
        i = int(np.searchsorted(ref, self._cursor_x))
        i = min(max(i + direction, 0), len(ref) - 1)
        self.set_cursor_x(float(ref[i]), snap=False)
        # przy przybliżeniu kursor nie może wyjechać za ekran — widok jedzie za nim
        self.ensure_visible(self._cursor_x)

    def clear_pin(self):
        self._pinned = False
        self.pinChanged.emit(False)
        if self._cursor_x is not None:
            self._refresh_cursor_items()

    def _snap_x(self, x: float) -> float:
        vis = [s for s in self.visible_series() if len(s.lx)]
        if not vis:
            return x
        ref = np.unique(np.concatenate([s.lx[np.isfinite(s.lx)] for s in vis]))
        if not len(ref):
            return x
        i = int(np.searchsorted(ref, x))
        i = min(max(i, 0), len(ref) - 1)
        if i > 0 and abs(ref[i - 1] - x) <= abs(ref[i] - x):
            i -= 1
        return float(ref[i])

    def _refresh_cursor_items(self):
        x = self._cursor_x
        vis = self.visible_series()
        if x is None or not vis:
            self.vline.hide()
            self.tooltip.hide()
            self.marker_label.hide()
            self.axis_badge.hide()
            self._crosshair_h.hide()
            for s in self._series.values():
                if s.dots is not None:
                    s.dots.hide()
            return

        self.vline.setPos(x)
        self.vline.show()
        self._crosshair_h.hide()
        for s in self._series.values():
            if s.dots is not None:
                s.dots.setVisible(s.visible)

        # punkty na przecięciu kursora z każdą serią + dane do dymku
        rows = []
        for s in vis:
            if not len(s.lx):
                continue
            # najbliższa próbka pod kursorem — w trybie RPM szukamy po obrotach,
            # bo ta sama wartość obrotów występuje w kilku przebiegach
            i = int(np.argmin(np.abs(s.lx - x)))
            real = float(s.ly[i]) if i < len(s.ly) else float("nan")
            plotted = self._plotted_value(s, real)
            s.dots.setData([x], [plotted])
            rows.append((s.spec, real))

        self.marker_label.hide()
        self._build_tooltip(x, rows)
        self._place_tooltip(x)
        self._update_badge(x)

    def _plotted_value(self, s: _Series, value: float) -> float:
        """Wartość w układzie wykresu (z uwzględnieniem normalizacji)."""
        if not self._normalized:
            return value
        span = s.ymax - s.ymin
        if span <= 0 or not np.isfinite(value):
            return 0.0
        return (value - s.ymin) / span * 100.0

    # ---------------------------------------------------- etykieta przy osi X
    def _fmt_x(self, x: float, time_decimals: int = 2) -> str:
        """Wartość osi X: obroty to liczba całkowita („3 200 obr/min”), czas z miejscami."""
        return fmt_num(x, 0 if self._x_is_rpm() else time_decimals)

    def _x_is_rpm(self) -> bool:
        return "obr" in self._x_unit

    def _badge_text(self, x: float) -> str:
        primary = f"{self._fmt_x(x)} {self._x_unit}".strip()
        if self._secondary_fn is not None:
            try:
                extra = self._secondary_fn(x)
            except Exception:
                extra = None
            if extra:
                return f"{primary} &nbsp;•&nbsp; {extra}"
        return primary

    def _update_badge(self, x: float):
        self.axis_badge.setText(self._badge_text(x))
        self.axis_badge.adjustSize()
        try:
            y0 = self.plot.vb.viewRange()[1][0]
            pt = self.plot.vb.mapViewToScene(QtCore.QPointF(x, y0))
            w = self.pw.mapFromScene(pt)
        except Exception:
            return
        bw, bh = self.axis_badge.width(), self.axis_badge.height()
        px = int(w.x() - bw / 2)
        px = max(4, min(px, max(4, self.pw.width() - bw - 4)))
        py = int(w.y() - bh - 5)
        self.axis_badge.move(px, py)
        self.axis_badge.show()

    def _build_tooltip(self, x: float, rows: list[tuple[SeriesSpec, float]]):
        pin = " 📌" if self._pinned else ""
        head = (f"<div style='color:#9aa0a6; margin-bottom:5px;'>"
                f"{self._x_label()} = <b>{self._fmt_x(x, 3)}</b> {self._x_unit}{pin}</div>")
        trs = []
        for spec, val in rows:
            unit = f" {spec.unit}" if spec.unit else ""
            tag = f"<span style='color:#9aa0a6;'>{spec.tag} </span>" if spec.tag else ""
            trs.append(
                "<tr>"
                f"<td style='padding-right:7px;'><span style='background:{spec.color};'>&nbsp;&nbsp;&nbsp;</span></td>"
                f"<td style='padding-right:10px; color:#e8eaed;'>{tag}{spec.short}</td>"
                f"<td align='right' style='color:#ffffff;'><b>{fmt_num(val)}</b>"
                f"<span style='color:#9aa0a6;'>{unit}</span></td>"
                "</tr>"
            )
        self.tooltip.setText(head + "<table cellspacing='0' cellpadding='1'>" + "".join(trs) + "</table>")
        self.tooltip.adjustSize()
        self.tooltip.show()

    def _x_label(self) -> str:
        return "Obroty" if self._x_mode == "rpm" else "Czas"

    def _place_tooltip(self, x: float):
        try:
            pt = self.plot.vb.mapViewToScene(QtCore.QPointF(x, self.plot.vb.viewRange()[1][1]))
        except Exception:
            return
        w = self.pw.mapFromScene(pt)
        tw, th = self.tooltip.width(), self.tooltip.height()
        px = w.x() + 14
        if px + tw > self.pw.width() - 4:
            px = w.x() - tw - 14
        px = max(4, min(px, max(4, self.pw.width() - tw - 4)))
        py = max(6, min(w.y() + 6, max(6, self.pw.height() - th - 6)))
        self.tooltip.move(int(px), int(py))

    # ------------------------------------------------------------- zdarzenia
    def _on_range_changed(self):
        try:
            self.plot.getAxis("right").setRange(*self.plot.vb.viewRange()[1])
        except Exception:
            pass
        if self._cursor_x is not None:
            self._place_tooltip(self._cursor_x)
            self._update_badge(self._cursor_x)

    def _on_manual_range(self, *args):
        """Użytkownik sam przesunął/ przeskalował widok — nie nadpisujemy jego zoomu."""
        self._user_zoomed = True

    def _on_mouse_moved(self, pos):
        if self._pinned:
            return
        if not self.plot.sceneBoundingRect().contains(pos):
            return
        pt = self.plot.vb.mapSceneToView(pos)
        self.set_cursor_x(pt.x())

    def _on_mouse_clicked(self, ev):
        if ev.double():
            self.doubleClicked.emit()
            return
        if ev.button() != Qt.LeftButton:
            return
        if self._pinned:
            self.clear_pin()
            return
        if self._cursor_x is not None and self.plot.sceneBoundingRect().contains(ev.scenePos()):
            self._pinned = True
            self.pinChanged.emit(True)
            self._refresh_cursor_items()

    def eventFilter(self, obj, event):
        if obj is self.pw and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Left, Qt.Key_Right):
                self.step_cursor(-1 if key == Qt.Key_Left else 1)
                return True
            if key == Qt.Key_Escape:
                self.clear_pin()
                return True
        return super().eventFilter(obj, event)

    # -------------------------------------------------------------- eksport
    def set_plot_background(self, color: str):
        self.pw.setBackground(color)

    def refresh_theme(self, theme: Theme):
        """Odświeża kolory wykresu po zmianie motywu."""
        self.theme = theme
        self.pw.setBackground(theme.plot_bg)
        for axis in ("left", "right", "bottom"):
            self.plot.getAxis(axis).setPen(pg.mkPen(theme.border))
            self.plot.getAxis(axis).setTextPen(pg.mkPen(theme.text_dim))
        self.vline.setPen(pg.mkPen(theme.cursor, width=1.1, style=Qt.DashLine))
        self._crosshair_h.setPen(pg.mkPen(theme.grid, width=1, style=Qt.DotLine))
        self.marker_label.setColor(theme.text_dim)
        self.axis_badge.setStyleSheet(
            f"background:{theme.accent}; color:{theme.accent_text}; border-radius:6px;"
            "padding:3px 9px; font-weight:600;"
        )
        self.tooltip.setStyleSheet(
            f"background:{theme.tooltip_bg}; border:1px solid {theme.tooltip_border};"
            "border-radius:7px; padding:7px 9px; color:#e8eaed;"
        )

    def export_png(self, path: str) -> bool:
        try:
            exporter = pg.exporters.ImageExporter(self.plot)
            exporter.parameters()["width"] = 1920
            exporter.export(path)
            return True
        except Exception:
            pix = self.pw.grab()
            return bool(pix.save(path))
