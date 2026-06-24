from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QTextEdit, QSplitter, QPushButton, QComboBox,
)
from PyQt6.QtCore import Qt

from app.data.storage import load_all_results
from app.data.config import Config


STYLESHEET = """
QWidget { background: #000; color: #fff; font-size: 13px; }
QListWidget { background: #0a0a0a; border: 1px solid #333; }
QListWidget::item { padding: 6px 8px; }
QListWidget::item:selected { background: #1a1a1a; color: #fff; }
QListWidget::item:hover { background: #111; }
QTextEdit { background: #0a0a0a; border: 1px solid #333; color: #ccc; font-family: monospace; font-size: 13px; }
QPushButton { background: #111; color: #fff; border: 1px solid #444; padding: 5px 12px; }
QPushButton:hover { background: #1a1a1a; }
QComboBox { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
QComboBox::drop-down { border: none; }
"""


class ResultsBrowser(QWidget):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLESHEET)
        self._config = config
        self._results = []

        root = QVBoxLayout(self)
        root.setSpacing(8)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Sort by:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Date (newest first)", "Average damage (high to low)", "Weapon name"])
        self._sort_combo.currentIndexChanged.connect(self._apply_sort)
        controls.addWidget(self._sort_combo)
        controls.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load)
        controls.addWidget(refresh_btn)
        root.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        splitter.addWidget(self._list)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        splitter.addWidget(self._detail)

        splitter.setSizes([300, 500])
        root.addWidget(splitter)

        self.load()

    def load(self):
        self._results = load_all_results()
        self._apply_sort()

    def _apply_sort(self):
        idx = self._sort_combo.currentIndex()
        if idx == 0:
            self._results.sort(key=lambda r: r.get("date", ""), reverse=True)
        elif idx == 1:
            self._results.sort(key=lambda r: r.get("avg", 0), reverse=True)
        else:
            self._results.sort(key=lambda r: (r.get("weapon", ""), r.get("date", "")))
        self._populate_list()

    def _populate_list(self):
        self._list.clear()
        for r in self._results:
            weapon = r.get("weapon", "")
            caliber = r.get("caliber", "")
            avg = r.get("avg", 0)
            date = r.get("date", "")
            label = f"{weapon} [{caliber}]  avg {avg:.1f}%  {date}"
            item = QListWidgetItem(label)
            self._list.addItem(item)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._results):
            self._detail.clear()
            return
        r = self._results[row]
        shots = r.get("shots", [])
        weapon = r.get("weapon", "")
        caliber = r.get("caliber", "")
        date = r.get("date", "")
        avg = r.get("avg", 0)
        min_val = r.get("min_val", 0)
        max_val = r.get("max_val", 0)
        stddev = r.get("stddev", 0)

        lines = [f"[{weapon}] [{caliber}] - {date}", ""]
        for i, dmg in enumerate(shots, 1):
            pad = " " if i == 10 else "  "
            lines.append(f"Shot {i}:{pad}{dmg}%")
        lines.append("")
        lines.append(f"Average: {avg:.1f}% | Min: {min_val}% | Max: {max_val}% | StdDev: {stddev:.1f}%")
        self._detail.setPlainText("\n".join(lines))
