"""Okno główne aplikacji VCDS LogScope."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QSettings, Signal

from . import APP_NAME, APP_TITLE, __version__
from .compare import CompareView
from .formatting import fmt_num, fmt_time
from .logview import LogView
from .model import LogData
from .parser import parse_log
from .theme import DARK, LIGHT, THEMES, Theme, stylesheet


def app_icon() -> QtGui.QIcon:
    """Ikona aplikacji rysowana programowo (wykres z linią kursora)."""
    icon = QtGui.QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pix = QtGui.QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        s = size
        p.setBrush(QtGui.QBrush(QtGui.QColor("#1b1e24")))
        p.setPen(QtGui.QPen(QtGui.QColor("#2e333c"), max(1, s * 0.03)))
        p.drawRoundedRect(1, 1, s - 2, s - 2, s * 0.22, s * 0.22)
        pts = [(0.14, 0.78), (0.30, 0.58), (0.44, 0.66), (0.60, 0.30), (0.72, 0.38), (0.88, 0.16)]
        for color, idxs in (("#12a150", [0, 1, 2, 3]), ("#e5484d", [2, 3, 4, 5])):
            pen = QtGui.QPen(QtGui.QColor(color), max(1.2, s * 0.075))
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            path = QtGui.QPainterPath()
            path.moveTo(pts[idxs[0]][0] * s, pts[idxs[0]][1] * s)
            for i in idxs[1:]:
                path.lineTo(pts[i][0] * s, pts[i][1] * s)
            p.drawPath(path)
        pen = QtGui.QPen(QtGui.QColor("#e8eaed"), max(1, s * 0.04))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawLine(int(s * 0.62), int(s * 0.12), int(s * 0.62), int(s * 0.9))
        p.end()
        icon.addPixmap(pix)
    return icon


class CompareDialog(QtWidgets.QDialog):
    """Wybór logów do porównania (otwarte karty + pliki z dysku)."""

    def __init__(self, logs: list[LogData], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Porównaj logi")
        self.setMinimumWidth(560)
        self.logs: list[LogData] = list(logs)

        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Zaznacz co najmniej dwa logi. Parametry o tych samych nazwach i jednostkach "
            "zostaną nałożone na siebie (linia ciągła = log A, przerywana = log B)."
        )
        info.setWordWrap(True)
        info.setObjectName("hint")
        lay.addWidget(info)

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        lay.addWidget(self.list, 1)

        row = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("Dodaj pliki z dysku…")
        btn_add.clicked.connect(self._add_files)
        row.addWidget(btn_add)
        row.addStretch(1)
        box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        box.button(QtWidgets.QDialogButtonBox.Ok).setText("Porównaj")
        box.button(QtWidgets.QDialogButtonBox.Cancel).setText("Anuluj")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        row.addWidget(box)
        lay.addLayout(row)

        self._refresh()

    def _refresh(self):
        self.list.clear()
        for i, log in enumerate(self.logs):
            item = QtWidgets.QListWidgetItem(
                f"{log.meta.file_name}   —   {log.meta.summary() or log.path}"
            )
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, i)
            item.setToolTip(log.path)
            self.list.addItem(item)

    def _add_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Wybierz logi VCDS", "", "Logi VCDS (*.csv *.txt);;Wszystkie pliki (*)"
        )
        for path in paths:
            try:
                self.logs.append(parse_log(path))
            except Exception as exc:  # pragma: no cover - komunikat dla użytkownika
                QtWidgets.QMessageBox.warning(self, "Błąd wczytywania", f"{path}\n\n{exc}")
        self._refresh()

    def selected(self) -> list[LogData]:
        out = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.Checked:
                out.append(self.logs[int(item.data(Qt.UserRole))])
        return out


class MainWindow(QtWidgets.QMainWindow):
    """Główne okno: karty logów, porównanie, motyw, ostatnie pliki."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(app_icon())
        self.resize(1600, 980)
        self.setAcceptDrops(True)
        self.settings = QSettings("VCDS-LogScope", "VCDS-LogScope")

        theme_name = self.settings.value("theme", "dark")
        self.theme: Theme = THEMES.get(str(theme_name), DARK)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._build_empty_state())
        self.stack.addWidget(self.tabs)
        self.setCentralWidget(self.stack)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self.apply_theme(self.theme)

        self._restore_geometry()
        self._maybe_open_cli_files()

    # ------------------------------------------------------------------ budowa
    def _build_empty_state(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        label = QtWidgets.QLabel(
            "Przeciągnij tutaj plik CSV z VCDS\n\n"
            "…albo kliknij „Otwórz log” (Ctrl+O)\n\n"
            "Obsługiwane są logi z jedną, dwiema lub trzema grupami pomiarowymi\n"
            "(np. Grupa A: 031, Grupa B: 002, Grupa C: 011) — wykres nakładany,\n"
            "tabela z kolorowaniem i porównanie wielu logów."
        )
        label.setAlignment(Qt.AlignCenter)
        label.setObjectName("dropzone")
        lay.addStretch(1)
        lay.addWidget(label)
        lay.addStretch(1)
        return page

    def _build_actions(self):
        def act(text, shortcut, slot, tip=""):
            a = QtGui.QAction(text, self)
            if shortcut:
                a.setShortcut(shortcut)
            if tip:
                a.setToolTip(tip)
                a.setStatusTip(tip)
            a.triggered.connect(slot)
            return a

        self.act_open = act("&Otwórz log…", "Ctrl+O", self.open_files, "Otwórz plik CSV z VCDS")
        self.act_open_many = act("Otwórz kilka logów…", "Ctrl+Shift+O", self.open_files_multi)
        self.act_compare = act("&Porównaj logi…", "Ctrl+T", self.compare_logs,
                               "Nałóż dwa lub więcej logów i pokaż różnice")
        self.act_close = act("Zamknij kartę", "Ctrl+W", lambda: self._close_tab(self.tabs.currentIndex()))
        self.act_quit = act("Wyjdź", "Ctrl+Q", self.close)
        self.act_info = act("&Informacje o logu", "Ctrl+I", self.show_info)
        self.act_png = act("Zapisz wykres jako PNG…", "Ctrl+S", self.export_png)
        self.act_theme = act("Przełącz motyw (ciemny/jasny)", "Ctrl+D", self.toggle_theme)
        self.act_shortcuts = act("Skróty klawiszowe", "F1", self.show_shortcuts)
        self.act_about = act("O programie", "", self.show_about)

    def _build_menus(self):
        m_file = self.menuBar().addMenu("&Plik")
        m_file.addAction(self.act_open)
        m_file.addAction(self.act_open_many)
        self.menu_recent = m_file.addMenu("Ostatnio otwierane")
        m_file.addSeparator()
        m_file.addAction(self.act_compare)
        m_file.addAction(self.act_png)
        m_file.addSeparator()
        m_file.addAction(self.act_close)
        m_file.addAction(self.act_quit)

        m_view = self.menuBar().addMenu("&Widok")
        m_view.addAction(self.act_theme)
        m_view.addSeparator()
        for text, key in (("Wykres + tabela", "both"), ("Tylko wykres", "chart"), ("Tylko tabela", "table")):
            a = QtGui.QAction(text, self)
            a.triggered.connect(lambda _=False, k=key: self.set_view_mode(k))
            m_view.addAction(a)

        m_help = self.menuBar().addMenu("Pomo&c")
        m_help.addAction(self.act_info)
        m_help.addAction(self.act_shortcuts)
        m_help.addSeparator()
        m_help.addAction(self.act_about)
        self._refresh_recent()

    def _build_toolbar(self):
        tb = QtWidgets.QToolBar("Główny")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.addAction(self.act_open)
        tb.addAction(self.act_compare)
        tb.addSeparator()
        tb.addAction(self.act_info)
        tb.addAction(self.act_png)
        tb.addSeparator()
        tb.addAction(self.act_theme)
        self.addToolBar(tb)

    def _build_statusbar(self):
        self.lbl_file = QtWidgets.QLabel("brak logu")
        self.lbl_cursor = QtWidgets.QLabel("—")
        self.lbl_rpm = QtWidgets.QLabel("—")
        self.lbl_rows = QtWidgets.QLabel("")
        sb = self.statusBar()
        sb.addWidget(self.lbl_file, 1)
        sb.addPermanentWidget(QtWidgets.QLabel("kursor:"))
        sb.addPermanentWidget(self.lbl_cursor)
        sb.addPermanentWidget(QtWidgets.QLabel("obroty:"))
        sb.addPermanentWidget(self.lbl_rpm)
        sb.addPermanentWidget(self.lbl_rows)

    # ------------------------------------------------------------------ motyw
    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.setStyleSheet(stylesheet(theme))
        self.settings.setValue("theme", theme.name)
        self.act_theme.setText("Motyw: ciemny" if theme.is_dark else "Motyw: jasny")
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if hasattr(w, "apply_theme"):
                w.apply_theme(theme)

    def toggle_theme(self):
        self.apply_theme(LIGHT if self.theme.is_dark else DARK)

    # ------------------------------------------------------------------- pliki
    def _maybe_open_cli_files(self):
        import sys

        paths = [a for a in sys.argv[1:] if Path(a).suffix.lower() in (".csv", ".txt")]
        for p in paths:
            self.open_path(p)

    def open_files(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Otwórz log VCDS", "", "Logi VCDS (*.csv *.txt);;Wszystkie pliki (*)"
        )
        if path:
            self.open_path(path)

    def open_files_multi(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Otwórz logi VCDS", "", "Logi VCDS (*.csv *.txt);;Wszystkie pliki (*)"
        )
        for p in paths:
            self.open_path(p)

    def open_path(self, path: str):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, LogView) and Path(w.log.path) == Path(path):
                self.tabs.setCurrentIndex(i)
                return
        try:
            log = parse_log(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Nie udało się wczytać logu", f"{path}\n\n{exc}")
            return
        view = LogView(log, self.theme, self)
        view.cursorMoved.connect(self._on_cursor)
        view.apply_theme(self.theme)
        idx = self.tabs.addTab(view, Path(path).stem[:28])
        self.tabs.setTabToolTip(idx, path)
        self.tabs.setCurrentIndex(idx)
        self.stack.setCurrentIndex(1)
        self._add_recent(path)
        self._update_status(log)

    def _close_tab(self, index: int):
        if index < 0:
            return
        w = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if w is not None:
            w.deleteLater()
        if self.tabs.count() == 0:
            self.stack.setCurrentIndex(0)
            self.lbl_file.setText("brak logu")
            self.lbl_rows.setText("")
            self.lbl_cursor.setText("—")
            self.lbl_rpm.setText("—")

    def _on_tab_changed(self, index: int):
        w = self.tabs.widget(index) if index >= 0 else None
        if isinstance(w, LogView):
            self._update_status(w.log)

    def _update_status(self, log: LogData):
        self.lbl_file.setText(
            f"{log.meta.file_name}   •   {log.meta.summary()}   •   {log.meta.detail()}"
        )
        n = log.n_rows
        self.lbl_rows.setText(
            f"{n} wierszy  •  {len(log.groups)} grupy  •  {log.duration:.1f} s  "
            f"•  {len(log.numeric_channels)} parametrów"
        )

    def _on_cursor(self, t: float, rpm: float, _view):
        self.lbl_cursor.setText(f"{fmt_time(t)} s")
        self.lbl_rpm.setText(fmt_num(rpm) if rpm == rpm else "—")

    # -------------------------------------------------------------- porównanie
    def compare_logs(self):
        open_logs = [w.log for i in range(self.tabs.count())
                     if isinstance((w := self.tabs.widget(i)), LogView)]
        dlg = CompareDialog(open_logs, self)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        logs = dlg.selected()
        if len(logs) < 2:
            QtWidgets.QMessageBox.information(
                self, "Za mało logów", "Do porównania potrzebne są co najmniej dwa logi."
            )
            return
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CompareView) and w.logs and [l.path for l in w.logs] == [l.path for l in logs]:
                self.tabs.setCurrentIndex(i)
                return
        view = CompareView(logs, self.theme, self)
        view.cursorMoved.connect(self._on_cursor)
        idx = self.tabs.addTab(view, "Porównanie " + "+".join(view.tags))
        self.tabs.setTabToolTip(idx, "\n".join(l.path for l in logs))
        self.tabs.setCurrentIndex(idx)
        self.stack.setCurrentIndex(1)
        self.lbl_file.setText(f"Porównanie: " + "  vs  ".join(Path(l.path).name for l in logs))
        self.lbl_rows.setText(f"{len(view.params)} wspólnych parametrów  •  {len(view.grid)} wierszy siatki")

    # ------------------------------------------------------------------ widoki
    def set_view_mode(self, mode: str):
        w = self.tabs.widget(self.tabs.currentIndex())
        if not isinstance(w, LogView):
            return
        if mode == "chart":
            w.set_chart_visible(True)
            w.set_table_visible(False)
        elif mode == "table":
            w.set_chart_visible(False)
            w.set_table_visible(True)
        else:
            w.set_chart_visible(True)
            w.set_table_visible(True)

    def export_png(self):
        w = self.tabs.widget(self.tabs.currentIndex())
        if isinstance(w, (LogView, CompareView)):
            w._export_png()

    # ------------------------------------------------------------------ okna
    def show_info(self):
        w = self.tabs.widget(self.tabs.currentIndex())
        if not isinstance(w, LogView):
            QtWidgets.QMessageBox.information(self, "Informacje", "Otwórz log, aby zobaczyć informacje.")
            return
        log = w.log
        rows = [
            f"<b>Plik:</b> {log.path}",
            f"<b>Data:</b> {log.meta.date} {log.meta.time}",
            f"<b>Sterownik:</b> {log.meta.ecu}",
            f"<b>Silnik:</b> {log.meta.engine}",
            f"<b>VCDS:</b> {log.meta.vcds_version}  ({log.meta.data_version})",
            f"<b>Czas trwania:</b> {log.duration:.2f} s, wierszy: {log.n_rows}",
            "<br><b>Grupy i parametry:</b>",
        ]
        for g in log.groups:
            chans = ", ".join(f"{c.name} [{c.unit}]" for c in g.channels if c.has_data)
            rows.append(f"<b>Grupa {g.letter}: {g.group_id}</b> — {g.n_samples} próbek<br>{chans or '—'}")
        QtWidgets.QMessageBox.information(self, "Informacje o logu", "<br>".join(rows))

    def show_shortcuts(self):
        QtWidgets.QMessageBox.information(
            self,
            "Skróty klawiszowe",
            "<b>Ctrl+O</b> — otwórz log<br>"
            "<b>Ctrl+Shift+O</b> — otwórz kilka logów<br>"
            "<b>Ctrl+T</b> — porównaj logi<br>"
            "<b>Ctrl+W</b> — zamknij kartę<br>"
            "<b>Ctrl+I</b> — informacje o logu<br>"
            "<b>Ctrl+S</b> — zapisz wykres jako PNG<br>"
            "<b>Ctrl+D</b> — przełącz motyw<br><br>"
            "<b>←/→</b> — kursor o jedną próbkę<br>"
            "<b>klik</b> — przypnij kursor, <b>Esc</b> — odepnij<br>"
            "<b>rolka</b> — zoom osi X, <b>Ctrl+rolka</b> — zoom osi Y<br>"
            "<b>przeciąganie</b> — przesuwanie widoku, <b>dwuklik</b> — dopasuj",
        )

    def show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            f"O programie {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Czytelna wizualizacja logów z programu VCDS (VAG-COM).</p>"
            "<p>Wykres nakładany z kursorem pomiarowym, tabela z kolorowaniem narastającym, "
            "porównanie wielu logów (różnice parametrów).</p>"
            "<p>Zbudowano na PySide6 + pyqtgraph.</p>",
        )

    # ------------------------------------------------------------ ostatnie pliki
    def _add_recent(self, path: str):
        recent = self.settings.value("recent", [])
        if isinstance(recent, str):
            recent = [recent]
        recent = [r for r in recent if r != path]
        recent.insert(0, path)
        self.settings.setValue("recent", recent[:12])
        self._refresh_recent()

    def _refresh_recent(self):
        self.menu_recent.clear()
        recent = self.settings.value("recent", [])
        if isinstance(recent, str):
            recent = [recent]
        if not recent:
            a = QtGui.QAction("(brak)", self)
            a.setEnabled(False)
            self.menu_recent.addAction(a)
            return
        for path in recent[:12]:
            a = QtGui.QAction(Path(path).name + "   —   " + str(Path(path).parent), self)
            a.setToolTip(path)
            a.triggered.connect(lambda _=False, p=path: self.open_path(p))
            self.menu_recent.addAction(a)
        self.menu_recent.addSeparator()
        clear = QtGui.QAction("Wyczyść listę", self)
        clear.triggered.connect(lambda: (self.settings.setValue("recent", []), self._refresh_recent()))
        self.menu_recent.addAction(clear)

    # ------------------------------------------------------------- drag & drop
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        logs = []
        for p in paths:
            if Path(p).suffix.lower() in (".csv", ".txt"):
                logs.append(p)
        if not logs:
            return
        if len(logs) == 1:
            self.open_path(logs[0])
        else:
            for p in logs:
                self.open_path(p)
            answer = QtWidgets.QMessageBox.question(
                self, "Porównanie",
                f"Wczytano {len(logs)} logi. Czy otworzyć widok porównania?",
            )
            if answer == QtWidgets.QMessageBox.Yes:
                view = CompareView([w.log for i in range(self.tabs.count())
                                    if isinstance((w := self.tabs.widget(i)), LogView)][-len(logs):],
                                   self.theme, self)
                view.cursorMoved.connect(self._on_cursor)
                idx = self.tabs.addTab(view, "Porównanie " + "+".join(view.tags))
                self.tabs.setCurrentIndex(idx)
        event.acceptProposedAction()

    # ------------------------------------------------------------- geometria
    def _restore_geometry(self):
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event: QtGui.QCloseEvent):  # noqa: N802
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)
