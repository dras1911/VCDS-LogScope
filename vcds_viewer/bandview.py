"""Widok pasm — każdy parametr w osobnym poziomym pasie, wspólny kursor.

Rozwiązuje problem nakładania: przy 8–12 parametrach wspólny wykres staje się plątaniną,
a przy normalizacji wszystkie serie zajmują całą wysokość. Tutaj każdy parametr ma własny
pas z własną skalą, a kursor i wartości są wspólne dla wszystkich pasów.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pyqtgraph as pg
from .qt import Qt, QtCore, QtGui, QtWidgets, Signal

from .chartview import LogViewBox, SeriesSpec
from .formatting import fmt_num
from .theme import Theme


class _Lane:
    """Jeden pas: wykres + seria + linia kursora."""

    __slots__ = ("spec", "plot", "curve", "dots", "vline", "lx", "ly", "ymin", "ymax", "visible")

    def __init__(self, spec: SeriesSpec):
        self.spec = spec
        self.plot: Optional[pg.PlotItem] = None
        self.curve: Optional[pg.PlotDataItem] = None
        self.dots: Optional[pg.ScatterPlotItem] = None
        self.vline: Optional[pg.InfiniteLine] = None
        self.lx = np.asarray(spec.lookup_x if spec.lookup_x is not None else spec.x, dtype=float)
        self.ly = np.asarray(spec.lookup_y if spec.lookup_y is not None else spec.y, dtype=float)
        finite = self.ly[np.isfinite(self.ly)]
        self.ymin = float(finite.min()) if len(finite) else 0.0
        self.ymax = float(finite.max()) if len(finite) else 1.0
        self.visible = True


class BandsChart(QtWidgets.QWidget):
    """Stos pasm: jeden parametr = jeden wykres, wspólna oś X i wspólny kursor."""

    cursorMoved = Signal(float)
    doubleClicked = Signal()

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._lanes: dict[str, _Lane] = {}
        self._order: list[str] = []
        self._cursor_x: Optional[float] = None
        self._x_mode = "time"
        self._x_unit = "s"
        self._pinned = False
        self._user_zoomed = False
        self._snap = True

        pg.setConfigOptions(antialias=True, background=theme.plot_bg, foreground=theme.text_dim)

        self.glw = pg.GraphicsLayoutWidget(self)
        self.glw.setBackground(theme.plot_bg)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.glw)

        self.badge = QtWidgets.QLabel(self.glw)
        self.badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.badge.setTextFormat(Qt.RichText)
        self._style_badge()
        self.badge.hide()
        self._secondary_fn = None

        self.glw.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.glw.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        self.glw.installEventFilter(self)

    # ------------------------------------------------------------------ API
    def set_secondary_fn(self, fn):
        self._secondary_fn = fn

    def set_snap(self, on: bool):
        self._snap = on

    def set_x_axis(self, mode: str, unit: str, label: str):
        self._x_mode, self._x_unit = mode, unit
        self._axis_label = label
        for lane in self._lanes.values():
            if lane.plot is not None:
                lane.plot.getAxis("bottom").setLabel(label, units=unit)

    def clear(self):
        self._lanes.clear()
        self._order.clear()
        self._cursor_x = None
        self.badge.hide()
        self.glw.clear()

    def set_series(self, specs: list[SeriesSpec]):
        """Buduje pasy — po jednym na serię (kolejność jak w panelu parametrów)."""
        self.clear()
        for spec in specs:
            self._add_lane(spec)
        self._layout_axes()
        self._apply_visibility()
        self.fit()

    def _add_lane(self, spec: SeriesSpec):
        lane = _Lane(spec)
        row = len(self._lanes)
        plot = self.glw.addPlot(row=row, col=0, viewBox=LogViewBox(enableMenu=False))
        plot.setMenuEnabled(False)
        plot.showGrid(x=True, y=True, alpha=0.14)
        plot.getAxis("bottom").setPen(pg.mkPen(self.theme.border))
        plot.getAxis("left").setPen(pg.mkPen(self.theme.border))
        plot.getAxis("bottom").setTextPen(pg.mkPen(self.theme.text_dim))
        plot.getAxis("left").setTextPen(pg.mkPen(self.theme.text_dim))
        plot.getAxis("left").setWidth(64)
        plot.setTitle(self._title(spec), color=self.theme.text_dim, size="10pt")

        curve = pg.PlotDataItem(pen=pg.mkPen(spec.color, width=spec.width, style=spec.style),
                                antialias=True, connect="finite")
        curve.setZValue(10)
        plot.addItem(curve)
        curve.setClipToView(True)
        curve.setDownsampling(auto=True, method="peak")
        curve.setData(lane.spec.x, lane.spec.y)

        dots = pg.ScatterPlotItem(size=8, pen=pg.mkPen(spec.color, width=2),
                                  brush=pg.mkBrush(spec.color))
        dots.setZValue(30)
        dots.hide()
        plot.addItem(dots)

        vline = pg.InfiniteLine(angle=90, movable=False,
                                pen=pg.mkPen(self.theme.cursor, width=1.0, style=Qt.DashLine))
        vline.setZValue(50)
        vline.hide()
        plot.addItem(vline, ignoreBounds=True)

        lane.plot, lane.curve, lane.dots, lane.vline = plot, curve, dots, vline
        self._lanes[spec.sid] = lane
        self._order.append(spec.sid)

        first = next(iter(self._lanes.values())).plot
        if first is not None and first is not plot:
            plot.setXLink(first)

    def _layout_axes(self):
        """Oś X pokazujemy tylko pod ostatnim pasem, żeby nie zabierać miejsca."""
        lanes = [self._lanes[s] for s in self._order if s in self._lanes]
        for i, lane in enumerate(lanes):
            if lane.plot is None:
                continue
            last = i == len(lanes) - 1
            lane.plot.showAxis("bottom", show=last)
            lane.plot.getAxis("bottom").setStyle(showValues=last)

    def _title(self, spec: SeriesSpec, value: Optional[float] = None) -> str:
        # spec.short zawiera już jednostkę (np. „Napięcie [V]”) — nie dokładamy jej drugi raz.
        # Grupa w nawiasie jest potrzebna, gdy ten sam parametr występuje w dwóch grupach.
        name = f"{spec.short} · {spec.group}" if spec.group else spec.short
        head = f"<span style='color:{self.theme.text_dim}'>{name}</span>"
        if value is None or not np.isfinite(value):
            return head
        return f"{head}&nbsp;&nbsp;<b style='color:{self.theme.text}'>{fmt_num(value)}</b>"

    def set_series_visible(self, sid: str, visible: bool):
        lane = self._lanes.get(sid)
        if lane is None:
            return
        lane.visible = visible
        self._apply_visibility()
        self._layout_axes()
        if not self._user_zoomed:
            self.fit()
        if self._cursor_x is not None:
            self._refresh_cursor()

    def _apply_visibility(self):
        for lane in self._lanes.values():
            if lane.plot is not None:
                lane.plot.setVisible(lane.visible)

    def visible_lanes(self) -> list[_Lane]:
        return [self._lanes[s] for s in self._order
                if s in self._lanes and self._lanes[s].visible]

    def fit(self):
        self._user_zoomed = False
        lanes = self.visible_lanes()
        if not lanes:
            return
        xs = [lane.spec.x[np.isfinite(lane.spec.x)] for lane in lanes]
        xs = [a for a in xs if len(a)]
        if not xs:
            return
        xmin = min(float(a.min()) for a in xs)
        xmax = max(float(a.max()) for a in xs)
        if xmax <= xmin:
            xmax = xmin + 1
        for lane in lanes:
            if lane.plot is None:
                continue
            span = lane.ymax - lane.ymin
            pad = span * 0.08 if span > 0 else 1.0
            lane.plot.vb.setYRange(lane.ymin - pad, lane.ymax + pad, padding=0.0)
        first = next((lane.plot for lane in lanes if lane.plot is not None), None)
        if first is not None:
            first.vb.setXRange(xmin, xmax, padding=0.01)

    def zoom(self, factor: float):
        lanes = [lane for lane in self.visible_lanes() if lane.plot is not None]
        if not lanes:
            return
        rng = lanes[0].plot.vb.viewRange()[0]
        center = QtCore.QPointF((rng[0] + rng[1]) / 2, 0)
        for lane in lanes:
            lane.plot.vb.scaleBy((factor, 1.0), center=center)

    # ---------------------------------------------------------------- kursor
    def cursor_x(self) -> Optional[float]:
        return self._cursor_x

    def set_cursor_x(self, x: float, emit: bool = True, snap: bool = True):
        x = float(x)
        if snap and self._snap:
            lanes = self.visible_lanes()
            refs = [lane.lx[np.isfinite(lane.lx)] for lane in lanes]
            refs = [r for r in refs if len(r)]
            if refs:
                ref = np.unique(np.concatenate(refs))
                i = int(np.searchsorted(ref, x))
                i = min(max(i, 0), len(ref) - 1)
                if i > 0 and abs(ref[i - 1] - x) <= abs(ref[i] - x):
                    i -= 1
                x = float(ref[i])
        self._cursor_x = x
        self._refresh_cursor()
        if emit:
            self.cursorMoved.emit(x)

    def step_cursor(self, direction: int):
        lanes = self.visible_lanes()
        refs = [lane.lx[np.isfinite(lane.lx)] for lane in lanes]
        refs = [r for r in refs if len(r)]
        if not refs:
            return
        ref = np.unique(np.concatenate(refs))
        if self._cursor_x is None:
            self.set_cursor_x(float(ref[0]))
            return
        i = int(np.searchsorted(ref, self._cursor_x))
        i = min(max(i + direction, 0), len(ref) - 1)
        self.set_cursor_x(float(ref[i]), snap=False)

    def clear_pin(self):
        self._pinned = False
        if self._cursor_x is not None:
            self._refresh_cursor()

    def _refresh_cursor(self):
        x = self._cursor_x
        lanes = self.visible_lanes()
        if x is None or not lanes:
            for lane in self._lanes.values():
                if lane.vline is not None:
                    lane.vline.hide()
                if lane.dots is not None:
                    lane.dots.hide()
            self.badge.hide()
            return
        for lane in lanes:
            if lane.vline is not None:
                lane.vline.setPos(x)
                lane.vline.show()
            if not len(lane.lx):
                continue
            i = int(np.argmin(np.abs(lane.lx - x)))
            value = float(lane.ly[i]) if i < len(lane.ly) else float("nan")
            if lane.dots is not None:
                lane.dots.setData([x], [value])
                lane.dots.show()
            if lane.plot is not None:
                lane.plot.setTitle(self._title(lane.spec, value), color=self.theme.text_dim, size="10pt")
        self._update_badge(x)

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
        self.badge.setText(self._badge_text(x))
        self.badge.adjustSize()
        lanes = [lane for lane in self.visible_lanes() if lane.plot is not None]
        if not lanes:
            return
        last = lanes[-1].plot
        try:
            y0 = last.vb.viewRange()[1][0]
            pt = last.vb.mapViewToScene(QtCore.QPointF(x, y0))
            w = self.glw.mapFromScene(pt)
        except Exception:
            return
        bw, bh = self.badge.width(), self.badge.height()
        px = max(4, min(int(w.x() - bw / 2), max(4, self.glw.width() - bw - 4)))
        py = int(w.y() - bh - 5)
        self.badge.move(px, py)
        self.badge.show()

    # ------------------------------------------------------------- zdarzenia
    def _on_mouse_moved(self, pos):
        if self._pinned:
            return
        lanes = [lane for lane in self.visible_lanes() if lane.plot is not None]
        if not lanes:
            return
        plot = lanes[0].plot
        if not plot.sceneBoundingRect().contains(pos):
            return
        self.set_cursor_x(plot.vb.mapSceneToView(pos).x())

    def _on_mouse_clicked(self, ev):
        if ev.double():
            self.doubleClicked.emit()
            return
        if ev.button() != Qt.LeftButton:
            return
        if self._pinned:
            self.clear_pin()
            return
        lanes = [lane for lane in self.visible_lanes() if lane.plot is not None]
        if self._cursor_x is not None and lanes and \
                lanes[0].plot.sceneBoundingRect().contains(ev.scenePos()):
            self._pinned = True
            self._refresh_cursor()

    def eventFilter(self, obj, event):
        if obj is self.glw:
            et = event.type()
            if et == QtCore.QEvent.Resize:
                # po zmianie rozmiaru okna trzeba przeliczyć pozycję dymka kursora
                if self._cursor_x is not None:
                    self._update_badge(self._cursor_x)
            elif et == QtCore.QEvent.KeyPress:
                key = event.key()
                if key in (Qt.Key_Left, Qt.Key_Right):
                    self.step_cursor(-1 if key == Qt.Key_Left else 1)
                    return True
                if key == Qt.Key_Escape:
                    self.clear_pin()
                    return True
        return super().eventFilter(obj, event)

    # -------------------------------------------------------------- wygląd
    def _style_badge(self):
        self.badge.setStyleSheet(
            f"background:{self.theme.accent}; color:{self.theme.accent_text}; border-radius:6px;"
            "padding:3px 9px; font-weight:600;"
        )

    def refresh_theme(self, theme: Theme):
        self.theme = theme
        self.glw.setBackground(theme.plot_bg)
        self._style_badge()
        for lane in self._lanes.values():
            if lane.plot is None:
                continue
            for axis in ("left", "bottom"):
                lane.plot.getAxis(axis).setPen(pg.mkPen(theme.border))
                lane.plot.getAxis(axis).setTextPen(pg.mkPen(theme.text_dim))
            if lane.vline is not None:
                lane.vline.setPen(pg.mkPen(theme.cursor, width=1.0, style=Qt.DashLine))
            lane.plot.setTitle(self._title(lane.spec), color=theme.text_dim, size="10pt")

    def export_png(self, path: str) -> bool:
        try:
            pix = self.glw.grab()
            return bool(pix.save(path))
        except Exception:
            return False
