"""Warstwa zgodności Qt — ten sam kod działa na PySide6 (Qt 6) i PySide2 (Qt 5.15).

PySide6/Qt 6 wymaga Windows 10+. Dla starszych komputerów (Windows 7/8) budujemy tę samą
aplikację na PySide2/Qt 5.15 — różnice między wiązaniami są tu sprowadzone do jednego miejsca.
"""

from __future__ import annotations

QT_API: str

try:  # Qt 6 (nowoczesne systemy)
    from PySide6 import QtCore, QtGui, QtWidgets  # noqa: F401
    from PySide6.QtCore import QSettings, Qt, Signal, Slot  # noqa: F401

    QT_API = "PySide6"
except ImportError:  # Qt 5.15 (Windows 7/8)
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore  # noqa: F401
    from PySide2.QtCore import QSettings, Qt, Signal, Slot  # type: ignore  # noqa: F401

    QT_API = "PySide2"

# W Qt 5 QAction należy do QtWidgets, w Qt 6 do QtGui.
QAction = QtWidgets.QAction if QT_API == "PySide2" else QtGui.QAction

# W Qt 5 nie ma typu wyliczeniowego Qt.PenStyle — używamy zwykłego int.
PenStyle = getattr(Qt, "PenStyle", int)

__all__ = [
    "QT_API", "QtCore", "QtGui", "QtWidgets", "Qt", "Signal", "Slot",
    "QSettings", "QAction", "PenStyle",
]
