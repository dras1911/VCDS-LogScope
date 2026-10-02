"""Suwaki nawigacji pod wykresem: powiększenie i przesuwanie widoku.

Dla tych, którzy wolą wyraźny suwak od kółka myszy: „Powiększenie” przybliża
i oddala wykres w poziomie, a suwak widoku (taki jak pasek przewijania) przesuwa
oglądany fragment po całym logu. Oba suwaki odzwierciedlają na bieżąco stan
wykresu — kółko myszy, przyciski − / + i „Dopasuj” też je przestawiają.

Widget nie zna jednostek osi. Wykres przekazuje mu pełny zakres danych
(`set_domain`) oraz bieżący widok (`set_view`), a on odsyła sygnałem
`rangeRequested(x0, x1)` nowy zakres do ustawienia na ViewBoxie.
"""

from __future__ import annotations

import math
from typing import Optional

from .qt import Qt, QtWidgets, Signal


class ChartNavigator(QtWidgets.QWidget):
    """Pasek pod wykresem: [Powiększenie: ──●──] [przesuwanie ────●──────].

    * suwak powiększenia — lewo: cały log, prawo: maksymalne przybliżenie,
    * pasek przesuwania — pozycja oglądanego fragmentu; szerokość uchwytu
      pokazuje, jak duża część logu jest widoczna.
    """

    #: Nowy oglądany zakres osi X (w jednostkach osi) — do ustawienia na ViewBoxie.
    rangeRequested = Signal(float, float)

    ZOOM_STEPS = 1000          # rozdzielczość suwaka powiększenia
    MAX_ZOOM = 250.0           # pełny zakres / maksymalne przybliżenie suwaka
    VALUE_SCALE = 1000.0       # jednostki osi → liczby całkowite paska przewijania

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lo = 0.0
        self._hi = 1.0
        self._view: Optional[tuple[float, float]] = None

        self.lbl = QtWidgets.QLabel("Powiększenie")
        self.lbl.setObjectName("hint")

        self.zoom = QtWidgets.QSlider(Qt.Horizontal, self)
        self.zoom.setRange(0, self.ZOOM_STEPS)
        self.zoom.setFixedWidth(120)
        self.zoom.setToolTip(
            "Przybliżanie wykresu (w poziomie): przeciągnij w prawo, żeby powiększyć,\n"
            "w lewo, żeby oddalić. To samo robi kółko myszy, a przycisk „Dopasuj”\n"
            "(albo dwuklik na wykresie) wraca do całego logu."
        )

        self.scroll = QtWidgets.QScrollBar(Qt.Horizontal, self)
        self.scroll.setMinimumWidth(120)
        self.scroll.setToolTip(
            "Przesuwanie widoku: przeciągnij suwak, żeby dojechać do wybranego miejsca\n"
            "w logu; kliknięcie na torze przesuwa widok o jeden ekran, a strzałki —\n"
            "o niewielki krok. Szerokość uchwytu pokazuje poziom przybliżenia."
        )

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.lbl)
        row.addWidget(self.zoom)
        row.addWidget(self.scroll, 1)

        self.zoom.valueChanged.connect(self._on_zoom_changed)
        self.scroll.valueChanged.connect(self._on_scroll_changed)
        self.set_domain(None, None)

    # ------------------------------------------------------------- od wykresu
    def domain(self) -> Optional[tuple[float, float]]:
        """Pełny zakres danych przekazany przez wykres (albo None)."""
        if self._view is None:
            return None
        return self._lo, self._hi

    def set_domain(self, lo: Optional[float], hi: Optional[float]) -> None:
        """Pełny zakres danych (początek…koniec logu). None = brak danych."""
        if lo is None or hi is None or not (hi > lo):
            self._view = None
            self.setEnabled(False)
            return
        self._lo, self._hi = float(lo), float(hi)
        self.setEnabled(True)
        if self._view is None:
            self._view = (self._lo, self._hi)

    def set_view(self, x0: float, x1: float) -> None:
        """Bieżący widok — ustawia oba suwaki, nie emitując sygnałów."""
        if self._view is None or not (x1 > x0):
            return
        self._view = (float(x0), float(x1))
        self._sync_zoom()
        self._sync_scroll()

    # ------------------------------------------------------------- wewnętrzne
    @property
    def _domain_span(self) -> float:
        return max(self._hi - self._lo, 1e-9)

    def _zoom_value_for_span(self, span: float) -> int:
        if span >= self._domain_span:
            return 0
        frac = math.log(self._domain_span / max(span, 1e-12)) / math.log(self.MAX_ZOOM)
        return int(round(min(max(frac, 0.0), 1.0) * self.ZOOM_STEPS))

    def _span_for_zoom_value(self, value: int) -> float:
        frac = min(max(value, 0), self.ZOOM_STEPS) / self.ZOOM_STEPS
        return self._domain_span / (self.MAX_ZOOM ** frac)

    def _sync_zoom(self) -> None:
        span = self._view[1] - self._view[0]
        self.zoom.blockSignals(True)
        self.zoom.setValue(self._zoom_value_for_span(span))
        self.zoom.blockSignals(False)

    def _sync_scroll(self) -> None:
        x0, x1 = self._view
        total = self._domain_span * self.VALUE_SCALE
        page = max(x1 - x0, 0.0) * self.VALUE_SCALE
        maxval = max(0, int(round(total - min(page, total))))
        self.scroll.blockSignals(True)
        self.scroll.setRange(0, maxval)
        self.scroll.setPageStep(max(1, int(round(page))))
        self.scroll.setSingleStep(max(1, int(round(page / 10.0))))
        self.scroll.setValue(int(round((x0 - self._lo) * self.VALUE_SCALE)))
        self.scroll.blockSignals(False)

    def _clamped(self, x0: float, span: float) -> tuple[float, float]:
        span = min(max(span, 1e-9), self._domain_span)
        x0 = min(max(x0, self._lo), self._hi - span)
        return x0, x0 + span

    def _emit(self, x0: float, span: float) -> None:
        x0, x1 = self._clamped(x0, span)
        self._view = (x0, x1)          # zsynchronizuj własny stan od razu
        self.rangeRequested.emit(x0, x1)

    # ---------------------------------------------------------------- akcje
    def _on_zoom_changed(self, value: int) -> None:
        if self._view is None:
            return
        x0, x1 = self._view
        center = (x0 + x1) / 2.0
        span = self._span_for_zoom_value(value)
        self._emit(center - span / 2.0, span)

    def _on_scroll_changed(self, value: int) -> None:
        if self._view is None:
            return
        span = self._view[1] - self._view[0]
        self._emit(self._lo + value / self.VALUE_SCALE, span)
