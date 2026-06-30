from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QSplitter, QMessageBox,
)
from PyQt6.QtCore import Qt

from app.data.config import Config
from app.data.storage import load_all_results, HP_PER_PERCENT
from app.core.sync import SyncClient


STYLESHEET = """
QWidget { background: #000; color: #fff; font-size: 13px; }
QTreeWidget { background: #0a0a0a; border: 1px solid #333; }
QTreeWidget::item { padding: 4px 6px; }
QTreeWidget::item:selected { background: #1a1a1a; color: #fff; }
QTreeWidget::item:hover { background: #111; }
QTextEdit { background: #0a0a0a; border: 1px solid #333; color: #ccc;
            font-family: monospace; font-size: 13px; }
QPushButton { background: #111; color: #fff; border: 1px solid #444; padding: 5px 12px; }
QPushButton:hover { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #222; }
"""


class DamageResultsTab(QWidget):
    def __init__(self, config: Config, version: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLESHEET)
        self._config = config
        self._version = version
        self._results: list[dict] = []
        self._selected: dict | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load)
        top.addWidget(refresh_btn)
        root.addLayout(top)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._splitter.addWidget(self._tree)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setPlaceholderText("Select a test to view details")
        right_layout.addWidget(self._detail)

        if not config.permanent_optout_sync:
            self._upload_btn = QPushButton("Upload to community database")
            self._upload_btn.setEnabled(False)
            self._upload_btn.clicked.connect(self._on_upload)
            right_layout.addWidget(self._upload_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            self._upload_btn = None

        self._splitter.addWidget(right)

        self._splitter.setSizes([280, 520])
        root.addWidget(self._splitter)

        self.load()

    def load(self):
        self._results = load_all_results()
        self._populate_tree()

    def _populate_tree(self):
        self._tree.clear()

        groups: dict[str, dict[str, list[dict]]] = {}
        for r in self._results:
            w = r.get("weapon", "(unknown)")
            c = r.get("caliber", "(unknown)")
            groups.setdefault(w, {}).setdefault(c, []).append(r)

        for weapon in sorted(groups.keys()):
            weapon_item = QTreeWidgetItem([weapon])
            font = weapon_item.font(0)
            font.setBold(True)
            weapon_item.setFont(0, font)
            self._tree.addTopLevelItem(weapon_item)

            caliber_map = groups[weapon]
            for caliber in sorted(caliber_map.keys()):
                cal_item = QTreeWidgetItem([f"  {caliber}"])
                weapon_item.addChild(cal_item)

                entries = sorted(caliber_map[caliber], key=lambda r: r["date"], reverse=True)
                for r in entries:
                    date_str = r["date"].strftime("%Y-%m-%d %H:%M")
                    avg = r.get("avg", 0)
                    label = f"    {date_str}  avg {avg:.1f}%"
                    leaf = QTreeWidgetItem([label])
                    leaf.setData(0, Qt.ItemDataRole.UserRole, r)
                    cal_item.addChild(leaf)

            weapon_item.setExpanded(True)

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int):
        r = item.data(0, Qt.ItemDataRole.UserRole)
        if r is None:
            item.setExpanded(not item.isExpanded())
            return
        self._show_detail(r)

    def _show_detail(self, r: dict):
        self._selected = r
        if self._upload_btn is not None:
            self._upload_btn.setEnabled(self._config.sync_enabled)

        weapon = r.get("weapon", "")
        caliber = r.get("caliber", "")
        date = r.get("date", "")
        shots = r.get("shots", [])
        avg = r.get("avg", 0)
        min_val = r.get("min_val", 0)
        max_val = r.get("max_val", 0)
        stddev = r.get("stddev", 0)
        filepath = r.get("filepath", "")

        lines = [f"[{weapon}] [{caliber}] - {date}", ""]
        for i, dmg in enumerate(shots, 1):
            pad = " " if i < 10 else ""
            lines.append(f"  Shot {i}:{pad}  {dmg}% ({dmg * HP_PER_PERCENT} HP)")
        lines.append("")
        avg_hp = round(avg * HP_PER_PERCENT, 1)
        lines.append(
            f"  Average: {avg:.1f}% ({avg_hp} HP)"
            f" | Min: {min_val}% ({min_val * HP_PER_PERCENT} HP)"
            f" | Max: {max_val}% ({max_val * HP_PER_PERCENT} HP)"
            f" | StdDev: {stddev:.1f}% ({round(stddev * HP_PER_PERCENT, 1)} HP)"
        )
        if filepath:
            lines.append("")
            lines.append(f"  File: {filepath}")

        self._detail.setPlainText("\n".join(lines))

    def _on_upload(self):
        if self._selected is None or not self._config.sync_enabled:
            return
        ok = SyncClient(self._config, self._version).submit(self._selected)
        if ok:
            QMessageBox.information(self, "Uploaded", "Result uploaded to the community database.")
        else:
            QMessageBox.warning(self, "Upload failed", "Could not upload this result.")
