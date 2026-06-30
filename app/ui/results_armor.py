from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QSplitter, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget,
    QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.core.suspend import load_all_suspended, delete_suspend
from app.core.sync import SyncClient
from app.data.config import Config
from app.data.storage import load_all_armor_results

try:
    import pyqtgraph as pg
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

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
QTableWidget { background: #0a0a0a; border: 1px solid #333; gridline-color: #222; }
QTableWidget::item { padding: 3px 6px; }
QTableWidget::item:selected { background: #1a1a1a; }
QHeaderView::section { background: #111; color: #888; border: 1px solid #333; padding: 4px; }
QFrame#sep { color: #333; }
QLabel#in_progress_header { color: #aaa; font-size: 12px; padding: 4px 0; }
"""


def _sep() -> QFrame:
    f = QFrame()
    f.setObjectName("sep")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def _na(v, suffix="") -> str:
    return "N/A" if v is None else f"{v}{suffix}"


class ArmorResultsTab(QWidget):
    resume_requested = pyqtSignal(dict)

    def __init__(self, config: Config, version: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLESHEET)
        self._config = config
        self._version = version
        self._results: list[dict] = []
        self._suspended: list[dict] = []
        self._selected: dict | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._inprog_section = QWidget()
        ip_outer = QVBoxLayout(self._inprog_section)
        ip_outer.setContentsMargins(0, 0, 0, 0)
        ip_outer.setSpacing(4)

        ip_hdr = QLabel("In progress (suspended tests)")
        ip_hdr.setObjectName("in_progress_header")
        ip_outer.addWidget(ip_hdr)

        self._ip_scroll = QScrollArea()
        self._ip_scroll.setWidgetResizable(True)
        self._ip_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._ip_scroll.setMaximumHeight(160)

        self._ip_scroll_content = QWidget()
        self._ip_container = QVBoxLayout(self._ip_scroll_content)
        self._ip_container.setContentsMargins(0, 0, 0, 0)
        self._ip_container.setSpacing(2)
        self._ip_container.addStretch()
        self._ip_scroll.setWidget(self._ip_scroll_content)
        ip_outer.addWidget(self._ip_scroll)
        ip_outer.addWidget(_sep())

        root.addWidget(self._inprog_section)

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

        self._detail_stack = QStackedWidget()
        placeholder = QLabel("Select a test to view details")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #555;")
        self._detail_stack.addWidget(placeholder)
        self._detail_stack.addWidget(self._build_detail_widget())
        self._splitter.addWidget(self._detail_stack)

        self._splitter.setSizes([260, 540])
        root.addWidget(self._splitter)

        self.load()

    def _build_detail_widget(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        layout.addWidget(self._detail_text)

        self._chart_toggle_btn = QPushButton("Show chart")
        if not _HAS_PG:
            self._chart_toggle_btn.setEnabled(False)
        self._chart_toggle_btn.clicked.connect(self._toggle_detail_chart)
        layout.addWidget(self._chart_toggle_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._detail_right_stack = QStackedWidget()
        self._detail_right_stack.hide()

        if _HAS_PG:
            pg.setConfigOptions(antialias=False)
            self._detail_chart = pg.PlotWidget()
            self._detail_chart.setBackground("k")
            self._detail_chart.getAxis("bottom").setPen(pg.mkPen("w"))
            self._detail_chart.getAxis("left").setPen(pg.mkPen("w"))
            self._detail_chart.getAxis("bottom").setTextPen(pg.mkPen("w"))
            self._detail_chart.getAxis("left").setTextPen(pg.mkPen("w"))
            self._detail_pen_scatter = pg.ScatterPlotItem(
                pen=pg.mkPen("w"), brush=pg.mkBrush("w"), symbol="o", size=7
            )
            self._detail_blunt_scatter = pg.ScatterPlotItem(
                pen=pg.mkPen("w"), brush=pg.mkBrush(None), symbol="s", size=8
            )
            self._detail_chart.addItem(self._detail_pen_scatter)
            self._detail_chart.addItem(self._detail_blunt_scatter)
            self._detail_thresh_line = pg.InfiniteLine(
                pos=0, angle=0, pen=pg.mkPen("w", width=1, style=Qt.PenStyle.DashLine)
            )
            self._detail_chart.addItem(self._detail_thresh_line)
            self._detail_right_stack.addWidget(self._detail_chart)
        else:
            self._detail_right_stack.addWidget(QLabel("pyqtgraph not installed"))

        layout.addWidget(self._detail_right_stack)
        self._detail_show_chart = False

        if not self._config.permanent_optout_sync:
            self._upload_btn = QPushButton("Upload to community database")
            self._upload_btn.setEnabled(False)
            self._upload_btn.clicked.connect(self._on_upload)
            layout.addWidget(self._upload_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            self._upload_btn = None

        return w

    def _toggle_detail_chart(self):
        if not _HAS_PG:
            return
        self._detail_show_chart = not self._detail_show_chart
        if self._detail_show_chart:
            self._detail_right_stack.show()
            self._detail_text.hide()
            self._chart_toggle_btn.setText("Hide chart")
        else:
            self._detail_right_stack.hide()
            self._detail_text.show()
            self._chart_toggle_btn.setText("Show chart")

    def load(self):
        self._suspended = load_all_suspended()
        self._results = load_all_armor_results()
        self._populate_in_progress()
        self._populate_tree()

    def _populate_in_progress(self):
        while self._ip_container.count() > 1:
            item = self._ip_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._suspended:
            self._inprog_section.hide()
            return

        self._inprog_section.show()
        for s in self._suspended:
            row = QHBoxLayout()
            cal = s.get("caliber", "")
            grade = s.get("grade", "?")
            total = s.get("total_shots", 0)
            pen_count = s.get("pen_count", 0)
            pen_pct = round(pen_count / total * 100, 1) if total > 0 else 0.0
            dt = s.get("suspended_at", "")[:10]
            label = QLabel(
                f"{cal} vs Grade {grade}  -  {total} shots  -  pen {pen_pct}%  -  {dt}"
            )
            label.setStyleSheet("color: #bbb;")
            row.addWidget(label)
            row.addStretch()

            resume_btn = QPushButton("Resume")
            resume_btn.clicked.connect(lambda _checked=False, d=s: self.resume_requested.emit(d))
            row.addWidget(resume_btn)

            discard_btn = QPushButton("Discard")
            discard_btn.clicked.connect(lambda _checked=False, d=s: self._discard(d))
            row.addWidget(discard_btn)

            wrapper = QWidget()
            wrapper.setLayout(row)
            self._ip_container.insertWidget(self._ip_container.count() - 1, wrapper)

    def _discard(self, data: dict):
        cal = data.get("caliber", "")
        grade = data.get("grade", "?")
        reply = QMessageBox.question(
            self, "Discard suspended test",
            f"Discard suspended test for {cal} vs Grade {grade}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_suspend(cal, int(grade))
            self.load()

    def _populate_tree(self):
        self._tree.clear()

        groups: dict[str, dict[int, list[dict]]] = {}
        for r in self._results:
            cal = r.get("caliber", "(unknown)")
            grd = r.get("grade", 0)
            groups.setdefault(cal, {}).setdefault(grd, []).append(r)

        for caliber in sorted(groups.keys()):
            cal_item = QTreeWidgetItem([caliber])
            font = cal_item.font(0)
            font.setBold(True)
            cal_item.setFont(0, font)
            self._tree.addTopLevelItem(cal_item)

            grade_map = groups[caliber]
            for grade in sorted(grade_map.keys()):
                grade_item = QTreeWidgetItem([f"  Grade {grade}"])
                cal_item.addChild(grade_item)

                entries = sorted(grade_map[grade], key=lambda r: r["date"], reverse=True)
                for r in entries:
                    date_str = r["date"].strftime("%Y-%m-%d %H:%M")
                    pen_pct = r.get("pen_pct", 0.0)
                    margin = r.get("margin", 0.0)
                    label = f"    {date_str}  pen {pen_pct}%  ±{margin}%"
                    leaf = QTreeWidgetItem([label])
                    leaf.setData(0, Qt.ItemDataRole.UserRole, r)
                    grade_item.addChild(leaf)

            cal_item.setExpanded(True)

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

        cal = r.get("caliber", "")
        grade = r.get("grade", "?")
        date_str = r["date"].strftime("%Y-%m-%d %H:%M")
        filepath = r.get("filepath", "")

        pen_pct = r.get("pen_pct", 0.0)
        ci_lo = r.get("ci_lower", 0.0)
        ci_hi = r.get("ci_upper", 0.0)
        margin = r.get("margin", 0.0)
        total = r.get("total_shots", 0)
        pc = r.get("pen_count", 0)
        bc = r.get("blunt_count", 0)
        oc = r.get("override_count", 0)
        ovr_pct = round(oc / total * 100) if total > 0 else 0

        lines = [f"[{cal}] vs [Grade {grade}] - {date_str}", ""]
        if r.get("weapon_ref"):
            lines.append(f"Weapon reference: {r['weapon_ref']}")
        lines.append(f"Base damage: {r.get('base_damage', '?')}%  (source: {r.get('base_damage_source', 'manual')})")
        lines.append(f"Classification threshold: {r.get('threshold', '?')}%")
        lines.append("")
        lines.append(f"Total shots: {total}  |  Pens: {pc}  |  Blunts: {bc}  |  Overrides: {oc}")
        lines.append("")
        lines.append(f"Pen chance: {pen_pct}%  (90% CI: {ci_lo}% - {ci_hi}%,  margin ±{margin}%)")
        lines.append("")
        lines.append(f"Avg pen damage:   {_na(r.get('avg_pen_damage'), '%')}  |  Pen multiplier:   {_na(r.get('pen_multiplier'), 'x')}")
        lines.append(f"Avg blunt damage: {_na(r.get('avg_blunt_damage'), '%')}  |  Blunt multiplier: {_na(r.get('blunt_multiplier'), 'x')}")
        if oc > 0 and ovr_pct > 30:
            lines.append("")
            lines.append(f"Warning: high override rate ({ovr_pct}%) - base damage reference may be inaccurate")
        lines.append("")
        lines.append("Shot log:")
        for i, shot in enumerate(r.get("shots", []), 1):
            ov_mark = " *" if shot.get("overridden") else ""
            lines.append(f"  {i:>4}  {shot['damage']:>3}%  {shot['classification']}{ov_mark}")
        if filepath:
            lines.append("")
            lines.append(f"File: {filepath}")

        self._detail_text.setPlainText("\n".join(lines))
        self._detail_text.show()
        self._detail_right_stack.hide()
        self._detail_show_chart = False
        self._chart_toggle_btn.setText("Show chart")
        self._detail_stack.setCurrentIndex(1)

        if _HAS_PG:
            shots = r.get("shots", [])
            threshold = r.get("threshold", 0)
            pen_x = [i+1 for i, s in enumerate(shots) if s["classification"] == "pen"]
            pen_y = [s["damage"] for s in shots if s["classification"] == "pen"]
            blunt_x = [i+1 for i, s in enumerate(shots) if s["classification"] == "blunt"]
            blunt_y = [s["damage"] for s in shots if s["classification"] == "blunt"]
            self._detail_pen_scatter.setData(pen_x, pen_y)
            self._detail_blunt_scatter.setData(blunt_x, blunt_y)
            self._detail_thresh_line.setValue(threshold)

    def _on_upload(self):
        if self._selected is None or not self._config.sync_enabled:
            return
        ok = SyncClient(self._config, self._version).submit_armor(self._selected)
        if ok:
            QMessageBox.information(self, "Uploaded", "Result uploaded to the community database.")
        else:
            QMessageBox.warning(self, "Upload failed", "Could not upload this result.")
