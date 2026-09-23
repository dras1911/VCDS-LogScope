"""Wykres nakładany w stylu TuneZilla: wiele serii, linia kursora, dymek wartości."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

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
    x: np.ndarray
    y: np.ndarray
    style: Qt.PenStyle = Qt.SolidLine
    width: float = 1.7
    tag: str = ""                  # np. "Log A" / "Log B" (tryb porównania)
    group: str = ""


class _Series:
    __slots__ = ("spec", "curve", "dots", "visible", "px", "py", "ymin", "ymax")

    def __init__(self, spec: SeriesSpec):
        self.spec = spec
        self.curve: Optional[pg.PlotDataItem] = None
        self.dots: Optional[pg.ScatterPlotItem] = None
        self.visible = True
        self.px = np.asarray(spec.x, dtype=float)
        self.py = np.asarray(spec.y, dtype=float)
        self.ymin = float(np.nanmin(self.py)) if len(self.py) else 0.0
        self.ymax = float(np.nanmax(self.py)) if len(self.py) else 1.0


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
        # UWAGA: kolejność ma znaczenie — najpierw dodajemy krzywą do wykresu,
        # dopiero potem włączamy clipToView (inaczej pyqtgraph cache'uje zły ViewBox).
        s.curve = pg.PlotDataItem(pen=pen, antialias=True, connect="finite")
        s.curve.setZValue(10)
        self.plot.addItem(s.curve)
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

    def fit(self):
        """Dopasowuje widok do widocznych danych."""
        self._user_zoomed = False
        vis = self.visible_series()
        if not vis:
            return
        xmin = min(float(np.nanmin(s.px)) for s in vis if len(s.px))
        xmax = max(float(np.nanmax(s.px)) for s in vis if len(s.px))
        ymin = min(float(np.nanmin(self._plotted_y(s))) for s in vis if len(s.py))
        ymax = max(float(np.nanmax(self._plotted_y(s))) for s in vis if len(s.py))
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
        vis = [s for s in self.visible_series() if len(s.px)]
        if not vis:
            return
        ref = np.unique(np.concatenate([s.px for s in vis]))
        if self._cursor_x is None:
            self.set_cursor_x(ref[0])
            return
        i = int(np.searchsorted(ref, self._cursor_x))
        i = min(max(i + direction, 0), len(ref) - 1)
        self.set_cursor_x(float(ref[i]), snap=False)

    def clear_pin(self):
        self._pinned = False
        self.pinChanged.emit(False)
        if self._cursor_x is not None:
            self._refresh_cursor_items()

    def _snap_x(self, x: float) -> float:
        vis = [s for s in self.visible_series() if len(s.px)]
        if not vis:
            return x
        ref = np.unique(np.concatenate([s.px for s in vis]))
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
            if not len(s.px):
                continue
            i = int(np.searchsorted(s.px, x))
            i = min(max(i, 0), len(s.px) - 1)
            if i > 0 and abs(s.px[i - 1] - x) <= abs(s.px[i] - x):
                i -= 1
            px, py = float(s.px[i]), float(self._plotted_y(s)[i])
            s.dots.setData([px], [py])
            real = float(s.spec.y[i]) if i < len(s.spec.y) else float("nan")
            rows.append((s.spec, real))

        self.marker_label.hide()
        self._build_tooltip(x, rows)
        self._place_tooltip(x)
        self._update_badge(x)

    # ---------------------------------------------------- etykieta przy osi X
    def _badge_text(self, x: float) -> str:
        primary = f"{fmt_num(x, 2)} {self._x_unit}".strip()
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
                f"{self._x_label()} = <b>{fmt_num(x, 3)}</b> {self._x_unit}{pin}</div>")
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
