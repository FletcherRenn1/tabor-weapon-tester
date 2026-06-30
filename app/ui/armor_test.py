from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QStackedWidget, QMessageBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.core.armor_session import ArmorSession, ArmorState
from app.core.suspend import load_all_suspended
from app.core.tts import TTSEngine
from app.data.config import Config
from app.data.storage import load_all_results

try:
    import pyqtgraph as pg
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

STYLESHEET = """
QWidget { background: #000; color: #fff; font-size: 13px; }
QPushButton {
    background: #111; color: #fff; border: 1px solid #444; padding: 6px 14px;
}
QPushButton:hover { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #222; }
QLineEdit { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
QComboBox { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
QSpinBox, QDoubleSpinBox { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
QTableWidget { background: #0a0a0a; border: 1px solid #333; gridline-color: #222; }
QTableWidget::item { padding: 3px 6px; }
QTableWidget::item:selected { background: #1a1a1a; }
QHeaderView::section { background: #111; color: #888; border: 1px solid #333; padding: 4px; }
QLabel#stat_val { color: #fff; font-size: 14px; }
QLabel#stat_key { color: #666; font-size: 12px; }
QLabel#state_lbl { font-size: 16px; padding: 6px 0; }
QLabel#warn { color: #ff8; font-size: 12px; }
QFrame#sep { color: #222; }
QScrollArea { border: none; }
"""


def _sep() -> QFrame:
    f = QFrame()
    f.setObjectName("sep")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def _kv(key: str, val_default: str = "") -> tuple[QLabel, QLabel]:
    k = QLabel(key)
    k.setObjectName("stat_key")
    v = QLabel(val_default)
    v.setObjectName("stat_val")
    return k, v


def _na(v) -> str:
    return "N/A" if v is None else str(v)


class ArmorSetupWidget(QWidget):
    start_test = pyqtSignal(dict)
    resume_test = pyqtSignal(dict)
    back = pyqtSignal()

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLESHEET)
        self._config = config
        self._test_results_by_caliber: dict[str, list[dict]] = {}
        self._suspended: list[dict] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Caliber:"))
        self._caliber_edit = QLineEdit()
        self._caliber_edit.setPlaceholderText("e.g. 5.45x39")
        self._caliber_edit.textChanged.connect(self._on_caliber_changed)
        layout.addWidget(self._caliber_edit)

        layout.addWidget(QLabel("Armor grade:"))
        self._grade_combo = QComboBox()
        for g in range(1, 7):
            self._grade_combo.addItem(f"Grade {g}", g)
        layout.addWidget(self._grade_combo)

        layout.addWidget(QLabel("Base damage reference:"))
        self._base_combo = QComboBox()
        self._base_combo.currentIndexChanged.connect(self._on_base_changed)
        layout.addWidget(self._base_combo)

        self._manual_row = QHBoxLayout()
        self._manual_row.addWidget(QLabel("Base damage (%):"))
        self._manual_spin = QSpinBox()
        self._manual_spin.setRange(1, 100)
        self._manual_spin.setValue(30)
        self._manual_spin.valueChanged.connect(self._update_threshold_default)
        self._manual_row.addWidget(self._manual_spin)
        self._manual_row.addStretch()
        self._manual_widget = QWidget()
        self._manual_widget.setLayout(self._manual_row)
        layout.addWidget(self._manual_widget)

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Classification threshold (%):"))
        self._thresh_spin = QDoubleSpinBox()
        self._thresh_spin.setRange(0.1, 99.0)
        self._thresh_spin.setDecimals(1)
        self._thresh_spin.setValue(6.0)
        thresh_row.addWidget(self._thresh_spin)
        thresh_row.addStretch()
        layout.addLayout(thresh_row)

        layout.addWidget(QLabel("Weapon reference (optional):"))
        self._weapon_edit = QLineEdit()
        self._weapon_edit.setPlaceholderText("e.g. AK-74")
        layout.addWidget(self._weapon_edit)

        layout.addWidget(_sep())

        btns = QHBoxLayout()
        self._start_btn = QPushButton("Start test")
        self._start_btn.clicked.connect(self._on_start)
        btns.addWidget(self._start_btn)
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.back)
        btns.addWidget(back_btn)
        layout.addLayout(btns)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._populate_base_combo("")

    def refresh(self):
        self._suspended = load_all_suspended()
        all_results = load_all_results()
        self._test_results_by_caliber = {}
        for r in all_results:
            cal = r.get("caliber", "")
            self._test_results_by_caliber.setdefault(cal, []).append(r)
        self._on_caliber_changed(self._caliber_edit.text())

    def _on_caliber_changed(self, text: str):
        self._populate_base_combo(text.strip())

    def _populate_base_combo(self, caliber: str):
        self._base_combo.blockSignals(True)
        self._base_combo.clear()
        tests = self._test_results_by_caliber.get(caliber, [])
        for t in tests:
            label = f"{t['weapon']}  avg {t['avg']:.1f}%  ({t['date'].strftime('%Y-%m-%d')})"
            self._base_combo.addItem(label, round(t["avg"]))
        self._base_combo.addItem("Enter manually", None)
        if self._config.armor_base_damage_mode == "manual" or not tests:
            self._base_combo.setCurrentIndex(self._base_combo.count() - 1)
        else:
            self._base_combo.setCurrentIndex(0)
        self._base_combo.blockSignals(False)
        self._on_base_changed(self._base_combo.currentIndex())

    def _on_base_changed(self, _idx: int):
        val = self._base_combo.currentData()
        is_manual = val is None
        self._manual_widget.setVisible(is_manual)
        if not is_manual:
            self._manual_spin.setValue(int(val))
        self._update_threshold_default()

    def _base_damage_value(self) -> int:
        val = self._base_combo.currentData()
        if val is None:
            return self._manual_spin.value()
        return int(val)

    def _update_threshold_default(self):
        bd = self._base_damage_value()
        default_pct = self._config.armor_default_threshold_pct
        self._thresh_spin.setValue(round(bd * default_pct / 100.0, 1))

    def _on_start(self):
        caliber = self._caliber_edit.text().strip()
        if not caliber:
            QMessageBox.warning(self, "Missing info", "Enter a caliber.")
            self._caliber_edit.setFocus()
            return

        grade = self._grade_combo.currentData()

        existing = next(
            (s for s in self._suspended if s["caliber"] == caliber and s["grade"] == grade),
            None,
        )
        if existing:
            reply = QMessageBox.question(
                self,
                "Suspended test found",
                f"A suspended test exists for {caliber} vs Grade {grade} "
                f"({existing.get('total_shots', 0)} shots recorded).\n\n"
                "Resume it, or discard and start fresh?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.resume_test.emit(existing)
                return

        val = self._base_combo.currentData()
        is_manual = val is None
        base_damage = self._base_damage_value()
        source = "manual" if is_manual else self._base_combo.currentText()
        thresh = round(self._thresh_spin.value())

        self._config.armor_base_damage_mode = "manual" if is_manual else "last_test"
        self._config.save()

        self.start_test.emit({
            "caliber": caliber,
            "grade": grade,
            "base_damage": base_damage,
            "threshold": thresh,
            "weapon_ref": self._weapon_edit.text().strip(),
            "base_damage_source": source,
        })


class ArmorTestWidget(QWidget):
    cancel_requested = pyqtSignal()
    suspend_requested = pyqtSignal()
    finalise_requested = pyqtSignal()

    def __init__(self, tts: TTSEngine, config: Config, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLESHEET)
        self._tts = tts
        self._config = config
        self._session: ArmorSession | None = None
        self._show_chart = False
        self._shots_data: list[dict] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        left = QWidget()
        left.setFixedWidth(260)
        left_outer = QVBoxLayout(left)
        left_outer.setContentsMargins(0, 0, 0, 0)
        left_outer.setSpacing(0)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)

        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 0, 4)
        left_layout.setSpacing(4)

        _, self._lbl_caliber = _kv("Caliber / Grade")
        _, self._lbl_base = _kv("Base damage")
        _, self._lbl_thresh = _kv("Threshold")
        left_layout.addWidget(self._lbl_caliber)
        left_layout.addWidget(self._lbl_base)
        left_layout.addWidget(self._lbl_thresh)
        left_layout.addWidget(_sep())

        _, self._lbl_shots = _kv("Shots")
        _, self._lbl_estimate = _kv("Shots to finish")
        left_layout.addWidget(self._lbl_shots)
        left_layout.addWidget(self._lbl_estimate)
        left_layout.addWidget(_sep())

        _, self._lbl_pen_pct = _kv("Pen chance")
        _, self._lbl_ci = _kv("90% CI")
        _, self._lbl_margin = _kv("CI margin")
        left_layout.addWidget(self._lbl_pen_pct)
        left_layout.addWidget(self._lbl_ci)
        left_layout.addWidget(self._lbl_margin)
        left_layout.addWidget(_sep())

        _, self._lbl_avg_pen = _kv("Avg pen damage")
        _, self._lbl_pen_mult = _kv("Pen multiplier")
        _, self._lbl_avg_blunt = _kv("Avg blunt damage")
        _, self._lbl_blunt_mult = _kv("Blunt multiplier")
        left_layout.addWidget(self._lbl_avg_pen)
        left_layout.addWidget(self._lbl_pen_mult)
        left_layout.addWidget(self._lbl_avg_blunt)
        left_layout.addWidget(self._lbl_blunt_mult)
        left_layout.addWidget(_sep())

        _, self._lbl_overrides = _kv("Overrides")
        self._warn_label = QLabel("")
        self._warn_label.setObjectName("warn")
        self._warn_label.setWordWrap(True)
        self._warn_label.hide()
        left_layout.addWidget(self._lbl_overrides)
        left_layout.addWidget(self._warn_label)
        left_layout.addWidget(_sep())

        self._state_label = QLabel("")
        self._state_label.setObjectName("state_lbl")
        self._state_label.setWordWrap(True)
        left_layout.addWidget(self._state_label)

        self._health_label = QLabel("")
        self._health_label.setObjectName("stat_key")
        left_layout.addWidget(self._health_label)

        left_layout.addStretch()
        left_scroll.setWidget(left_content)
        left_outer.addWidget(left_scroll)

        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(4)
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.clicked.connect(self._on_pause)
        self._suspend_btn = QPushButton("Suspend")
        self._suspend_btn.clicked.connect(self.suspend_requested)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._finalise_btn = QPushButton("Finalise")
        self._finalise_btn.clicked.connect(self.finalise_requested)
        self._finalise_btn.hide()
        btn_layout.addWidget(self._pause_btn)
        btn_layout.addWidget(self._suspend_btn)
        btn_layout.addWidget(self._finalise_btn)
        btn_layout.addWidget(self._cancel_btn)
        left_outer.addLayout(btn_layout)

        root.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self._toggle_btn = QPushButton("Show chart")
        if not _HAS_PG:
            self._toggle_btn.setEnabled(False)
            self._toggle_btn.setToolTip("pyqtgraph not installed")
        self._toggle_btn.clicked.connect(self._toggle_view)
        right_layout.addWidget(self._toggle_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._right_stack = QStackedWidget()
        right_layout.addWidget(self._right_stack)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "Damage", "Class.", "Override"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.cellClicked.connect(self._on_table_click)
        self._right_stack.addWidget(self._table)

        if _HAS_PG:
            pg.setConfigOptions(antialias=False)
            self._chart = pg.PlotWidget()
            self._chart.setBackground("k")
            self._chart.getAxis("bottom").setPen(pg.mkPen("w"))
            self._chart.getAxis("left").setPen(pg.mkPen("w"))
            self._chart.getAxis("bottom").setTextPen(pg.mkPen("w"))
            self._chart.getAxis("left").setTextPen(pg.mkPen("w"))
            self._chart.setLabel("bottom", "Shot #", color="w")
            self._chart.setLabel("left", "Damage %", color="w")
            self._pen_scatter = pg.ScatterPlotItem(
                pen=pg.mkPen("w"), brush=pg.mkBrush("w"), symbol="o", size=7
            )
            self._blunt_scatter = pg.ScatterPlotItem(
                pen=pg.mkPen("w"), brush=pg.mkBrush(None), symbol="s", size=8
            )
            self._chart.addItem(self._pen_scatter)
            self._chart.addItem(self._blunt_scatter)
            self._thresh_line = pg.InfiniteLine(
                pos=0, angle=0, pen=pg.mkPen("w", width=1, style=Qt.PenStyle.DashLine)
            )
            self._chart.addItem(self._thresh_line)
            self._right_stack.addWidget(self._chart)
        else:
            self._right_stack.addWidget(QLabel("pyqtgraph not installed - chart unavailable"))

        root.addWidget(right)

    def attach_session(self, session: ArmorSession):
        self._session = session
        self._shots_data = []
        self._table.setRowCount(0)
        if _HAS_PG:
            self._pen_scatter.setData([], [])
            self._blunt_scatter.setData([], [])

        session.state_changed.connect(self._on_state)
        session.shot_recorded.connect(self._on_shot)
        session.health_updated.connect(self._on_health)
        session.stats_updated.connect(self._on_stats)
        session.override_rate_warning.connect(self._on_override_warning)
        session.entered_review.connect(self._on_review)

    def sync_session_data(self):
        session = self._session
        if session is None:
            return

        self._lbl_caliber.setText(f"{session.caliber} vs Grade {session.grade}")
        self._lbl_base.setText(f"{session.base_damage}%")
        self._lbl_thresh.setText(f"{session.threshold}%")
        if _HAS_PG:
            self._thresh_line.setValue(session.threshold)

        for i, s in enumerate(session.shots):
            self._append_row(i + 1, s["damage"], s["classification"], s["overridden"])
        self._shots_data = list(session.shots)
        if self._shots_data:
            self._refresh_chart()
            self._on_stats(self._build_stats_from_data())

    def detach_session(self):
        if self._session is not None:
            try:
                self._session.state_changed.disconnect(self._on_state)
                self._session.shot_recorded.disconnect(self._on_shot)
                self._session.health_updated.disconnect(self._on_health)
                self._session.stats_updated.disconnect(self._on_stats)
                self._session.override_rate_warning.disconnect(self._on_override_warning)
                self._session.entered_review.disconnect(self._on_review)
            except RuntimeError:
                pass
        self._session = None

    def reset(self):
        self.detach_session()
        self._shots_data = []
        self._table.setRowCount(0)
        if _HAS_PG:
            self._pen_scatter.setData([], [])
            self._blunt_scatter.setData([], [])
        self._state_label.setText("")
        self._health_label.setText("")
        self._warn_label.hide()
        self._pause_btn.setText("Pause")
        self._pause_btn.show()
        self._suspend_btn.show()
        self._finalise_btn.hide()
        for lbl in (self._lbl_shots, self._lbl_estimate, self._lbl_pen_pct,
                    self._lbl_ci, self._lbl_margin, self._lbl_avg_pen,
                    self._lbl_pen_mult, self._lbl_avg_blunt, self._lbl_blunt_mult,
                    self._lbl_overrides):
            lbl.setText("")

    def _on_state(self, state_name: str):
        messages = {
            "WAITING_FOR_FULL_HEALTH": "Waiting - heal to 100%",
            "READY_TO_SHOOT": "Shoot now",
            "WAITING_FOR_HIT": "Tracking hit...",
            "RECORDING_VALUE": "Recording...",
            "HEAL_WARNING": "Heal up before next shot",
            "PAUSED": "Paused - heal to 100% to resume",
            "REVIEW": "REVIEW - finalise to save",
            "SUSPENDED": "Suspended",
        }
        self._state_label.setText(messages.get(state_name, state_name))

        if state_name == "READY_TO_SHOOT":
            self._tts.speak_event("shoot")
        elif state_name == "HEAL_WARNING":
            self._tts.speak_event("heal")
        elif state_name == "REVIEW":
            self._tts.speak_event("complete")

    def _on_shot(self, shot_num: int, classification: str, damage: int):
        self._shots_data.append({"damage": damage, "classification": classification, "overridden": False})
        self._append_row(shot_num, damage, classification, False)
        self._table.scrollToBottom()
        self._tts.speak_event("shot_classified", classification=classification)
        if self._session:
            stats = self._session.get_stats()
            total = stats["total"]
            accurate = total >= 30
            if shot_num % 25 == 0:
                self._tts.speak_event("ci_update", margin=stats["margin"])
            estimate_interval = 10 if accurate else 15
            if shot_num % estimate_interval == 0:
                self._tts.speak_event("shots_estimate", estimate=stats["shots_estimate"])
        if _HAS_PG:
            self._refresh_chart()

    def _on_health(self, health: int):
        self._health_label.setText(f"Health: {health}%")

    def _on_stats(self, stats: dict):
        total = stats["total"]
        self._lbl_shots.setText(f"Shot {total}")
        self._lbl_estimate.setText(stats["shots_estimate"])
        self._lbl_pen_pct.setText(f"{stats['pen_pct']}%")
        self._lbl_ci.setText(f"{stats['ci_lower']}% - {stats['ci_upper']}%")
        self._lbl_margin.setText(f"±{stats['margin']}%")
        self._lbl_avg_pen.setText(_na(stats["avg_pen_damage"]) + ("%" if stats["avg_pen_damage"] is not None else ""))
        self._lbl_pen_mult.setText(_na(stats["pen_multiplier"]) + ("x" if stats["pen_multiplier"] is not None else ""))
        self._lbl_avg_blunt.setText(_na(stats["avg_blunt_damage"]) + ("%" if stats["avg_blunt_damage"] is not None else ""))
        self._lbl_blunt_mult.setText(_na(stats["blunt_multiplier"]) + ("x" if stats["blunt_multiplier"] is not None else ""))
        oc = stats["override_count"]
        ovr_pct = f"  ({round(oc/total*100)}%)" if total > 0 else ""
        self._lbl_overrides.setText(f"{oc}{ovr_pct}")
        self._refresh_table_styles()

    def _on_override_warning(self):
        self._warn_label.setText("High override rate - base damage reference may be inaccurate")
        self._warn_label.show()

    def _on_review(self):
        self._pause_btn.hide()
        self._suspend_btn.hide()
        self._finalise_btn.show()

    def _on_pause(self):
        if self._session is None:
            return
        if self._session.current_state == ArmorState.PAUSED:
            self._session.resume()
            self._pause_btn.setText("Pause")
        else:
            self._session.pause()
            self._pause_btn.setText("Resume")

    def _on_cancel(self):
        reply = QMessageBox.question(
            self, "Cancel test",
            "Cancel armor test? All recorded shots will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.cancel_requested.emit()

    def _on_table_click(self, row: int, _col: int):
        if self._session is None:
            return
        if row < 0 or row >= len(self._shots_data):
            return
        current = self._shots_data[row]["classification"]
        new_cls = "blunt" if current == "pen" else "pen"
        self._session.override_shot(row, new_cls)
        self._shots_data[row]["classification"] = new_cls
        self._shots_data[row]["overridden"] = True
        self._update_table_row(row)
        if _HAS_PG:
            self._refresh_chart()

    def _toggle_view(self):
        if not _HAS_PG:
            return
        self._show_chart = not self._show_chart
        self._right_stack.setCurrentIndex(1 if self._show_chart else 0)
        self._toggle_btn.setText("Hide chart" if self._show_chart else "Show chart")

    def _append_row(self, shot_num: int, damage: int, classification: str, overridden: bool):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(str(shot_num)))
        self._table.setItem(row, 1, QTableWidgetItem(f"{damage}%"))
        self._table.setItem(row, 2, QTableWidgetItem(classification))
        self._table.setItem(row, 3, QTableWidgetItem("yes" if overridden else ""))
        if overridden:
            self._make_row_italic(row)

    def _update_table_row(self, row: int):
        if row >= len(self._shots_data):
            return
        s = self._shots_data[row]
        self._table.item(row, 2).setText(s["classification"])
        self._table.item(row, 3).setText("yes" if s["overridden"] else "")
        if s["overridden"]:
            self._make_row_italic(row)

    def _make_row_italic(self, row: int):
        font = QFont()
        font.setItalic(True)
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item:
                item.setFont(font)

    def _refresh_table_styles(self):
        for row in range(min(self._table.rowCount(), len(self._shots_data))):
            if self._shots_data[row].get("overridden"):
                self._make_row_italic(row)

    def _refresh_chart(self):
        if not _HAS_PG:
            return
        pen_x, pen_y, blunt_x, blunt_y = [], [], [], []
        for i, s in enumerate(self._shots_data):
            if s["classification"] == "pen":
                pen_x.append(i + 1)
                pen_y.append(s["damage"])
            else:
                blunt_x.append(i + 1)
                blunt_y.append(s["damage"])
        self._pen_scatter.setData(pen_x, pen_y)
        self._blunt_scatter.setData(blunt_x, blunt_y)

    def _build_stats_from_data(self) -> dict:
        total = len(self._shots_data)
        if total == 0:
            return {"total": 0, "pen_count": 0, "blunt_count": 0, "override_count": 0,
                    "pen_pct": 0.0, "ci_lower": 0.0, "ci_upper": 100.0, "margin": 50.0,
                    "avg_pen_damage": None, "avg_blunt_damage": None,
                    "pen_multiplier": None, "blunt_multiplier": None,
                    "shots_estimate": "estimating..."}
        if self._session:
            return self._session.get_stats()
        return {"total": total, "pen_count": 0, "blunt_count": 0, "override_count": 0,
                "pen_pct": 0.0, "ci_lower": 0.0, "ci_upper": 100.0, "margin": 50.0,
                "avg_pen_damage": None, "avg_blunt_damage": None,
                "pen_multiplier": None, "blunt_multiplier": None,
                "shots_estimate": "estimating..."}
