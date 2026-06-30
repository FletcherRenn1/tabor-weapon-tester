from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

from app.data.config import Config
from app.ui.results_damage import DamageResultsTab
from app.ui.results_armor import ArmorResultsTab


STYLESHEET = """
QMainWindow, QWidget { background: #000; color: #fff; font-size: 13px; }
QTabWidget::pane { border: 1px solid #333; background: #000; }
QTabBar::tab { background: #111; color: #888; padding: 8px 18px; border: 1px solid #333; }
QTabBar::tab:selected { background: #000; color: #fff; border-bottom: none; }
QPushButton { background: #111; color: #fff; border: 1px solid #444; padding: 5px 12px; }
QPushButton:hover { background: #1a1a1a; }
"""


class ResultsBrowserWindow(QMainWindow):
    resume_requested = pyqtSignal(dict)

    def __init__(self, config: Config, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Results browser")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(860, 540)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._damage_tab = DamageResultsTab(config, version)
        self._tabs.addTab(self._damage_tab, "Damage Tests")

        self._armor_tab = ArmorResultsTab(config, version)
        self._armor_tab.resume_requested.connect(self.resume_requested)
        self._tabs.addTab(self._armor_tab, "Armor Tests")

    def refresh(self):
        self._damage_tab.load()
        self._armor_tab.load()

    def show_armor_tab(self):
        self._tabs.setCurrentIndex(1)
