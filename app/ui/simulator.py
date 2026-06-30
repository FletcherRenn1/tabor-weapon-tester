from __future__ import annotations

import random

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLineEdit, QCheckBox, QFrame, QButtonGroup, QRadioButton,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from app.core.mock import MockHealthProvider


STYLESHEET = """
QWidget { background: #000; color: #fff; font-size: 13px; }
QPushButton {
    background: #111; color: #fff; border: 1px solid #444; padding: 5px 12px;
}
QPushButton:hover { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #222; }
QSlider::groove:horizontal { background: #333; height: 4px; }
QSlider::handle:horizontal { background: #fff; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QLineEdit { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #555; background: #111; }
QCheckBox::indicator:checked { background: #fff; }
QRadioButton::indicator { width: 12px; height: 12px; border: 1px solid #555; border-radius: 6px; background: #111; }
QRadioButton::indicator:checked { background: #fff; }
QDoubleSpinBox { background: #111; color: #fff; border: 1px solid #444; padding: 4px 6px; }
"""


class FigureDisplay(QWidget):
    def __init__(self):
        super().__init__()
        self._health = 100
        self.setMinimumSize(120, 180)

    def set_health(self, value: int):
        self._health = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx = w // 2

        if self._health > 66:
            color = QColor(100, 200, 100)
        elif self._health > 33:
            color = QColor(220, 180, 50)
        else:
            color = QColor(200, 60, 60)

        pen = QPen(color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawEllipse(cx - 18, 10, 36, 36)
        painter.drawLine(cx, 46, cx, 110)
        painter.drawLine(cx, 58, cx - 28, 90)
        painter.drawLine(cx, 58, cx + 28, 90)
        painter.drawLine(cx, 110, cx - 20, 150)
        painter.drawLine(cx, 110, cx + 20, 150)

        painter.setPen(QPen(QColor(255, 255, 255), 1))
        font = painter.font()
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(0, 65, w, 30, Qt.AlignmentFlag.AlignCenter, f"{self._health}%")


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #333;")
    return f


class SimulatorWindow(QWidget):
    def __init__(self, provider: MockHealthProvider):
        super().__init__(None, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Simulator")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumWidth(300)
        self._provider = provider
        self._damage_session_ref = None
        self._armor_session_ref = None

        root = QVBoxLayout(self)
        root.setSpacing(8)

        self._figure = FigureDisplay()
        root.addWidget(self._figure, alignment=Qt.AlignmentFlag.AlignCenter)

        self._state_label = QLabel("State: IDLE")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._state_label)

        self._health_label = QLabel("Health: 100")
        self._health_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._health_label)

        root.addWidget(_sep())

        root.addWidget(QLabel("Health:"))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(100)
        self._slider.valueChanged.connect(self._on_slider)
        root.addWidget(self._slider)

        root.addWidget(_sep())

        self._damage_panel = QWidget()
        dp_layout = QVBoxLayout(self._damage_panel)
        dp_layout.setContentsMargins(0, 0, 0, 0)
        dp_layout.setSpacing(6)
        dp_layout.addWidget(QLabel("Damage amount:"))
        self._damage_edit = QLineEdit("30")
        dp_layout.addWidget(self._damage_edit)
        shoot_btn = QPushButton("Shoot")
        shoot_btn.clicked.connect(self._shoot_damage)
        dp_layout.addWidget(shoot_btn)
        root.addWidget(self._damage_panel)

        self._armor_panel = QWidget()
        ap_layout = QVBoxLayout(self._armor_panel)
        ap_layout.setContentsMargins(0, 0, 0, 0)
        ap_layout.setSpacing(6)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Shot mode:"))
        self._auto_radio = QRadioButton("Auto RNG")
        self._manual_radio = QRadioButton("Manual")
        self._auto_radio.setChecked(True)
        self._mode_group = QButtonGroup()
        self._mode_group.addButton(self._auto_radio)
        self._mode_group.addButton(self._manual_radio)
        self._auto_radio.toggled.connect(self._update_armor_mode)
        mode_row.addWidget(self._auto_radio)
        mode_row.addWidget(self._manual_radio)
        ap_layout.addLayout(mode_row)

        self._auto_panel = QWidget()
        auto_layout = QVBoxLayout(self._auto_panel)
        auto_layout.setContentsMargins(0, 0, 0, 0)
        auto_layout.setSpacing(4)

        rng_row1 = QHBoxLayout()
        rng_row1.addWidget(QLabel("Pen chance (%):"))
        self._pen_chance_spin = QDoubleSpinBox()
        self._pen_chance_spin.setRange(0, 100)
        self._pen_chance_spin.setValue(50.0)
        self._pen_chance_spin.setDecimals(1)
        rng_row1.addWidget(self._pen_chance_spin)
        auto_layout.addLayout(rng_row1)

        rng_row2 = QHBoxLayout()
        rng_row2.addWidget(QLabel("Pen damage (%):"))
        self._auto_pen_dmg = QLineEdit("22")
        rng_row2.addWidget(self._auto_pen_dmg)
        auto_layout.addLayout(rng_row2)

        rng_row3 = QHBoxLayout()
        rng_row3.addWidget(QLabel("Blunt damage (%):"))
        self._auto_blunt_dmg = QLineEdit("11")
        rng_row3.addWidget(self._auto_blunt_dmg)
        auto_layout.addLayout(rng_row3)

        auto_shoot_btn = QPushButton("Shoot (RNG)")
        auto_shoot_btn.clicked.connect(self._shoot_armor_rng)
        auto_layout.addWidget(auto_shoot_btn)
        ap_layout.addWidget(self._auto_panel)

        self._manual_panel = QWidget()
        man_layout = QVBoxLayout(self._manual_panel)
        man_layout.setContentsMargins(0, 0, 0, 0)
        man_layout.setSpacing(4)

        m_row1 = QHBoxLayout()
        m_row1.addWidget(QLabel("Pen damage (%):"))
        self._man_pen_dmg = QLineEdit("22")
        m_row1.addWidget(self._man_pen_dmg)
        man_layout.addLayout(m_row1)

        m_row2 = QHBoxLayout()
        m_row2.addWidget(QLabel("Blunt damage (%):"))
        self._man_blunt_dmg = QLineEdit("11")
        m_row2.addWidget(self._man_blunt_dmg)
        man_layout.addLayout(m_row2)

        man_btns = QHBoxLayout()
        pen_btn = QPushButton("Shoot - Pen")
        pen_btn.clicked.connect(self._shoot_armor_pen)
        blunt_btn = QPushButton("Shoot - Blunt")
        blunt_btn.clicked.connect(self._shoot_armor_blunt)
        man_btns.addWidget(pen_btn)
        man_btns.addWidget(blunt_btn)
        man_layout.addLayout(man_btns)
        ap_layout.addWidget(self._manual_panel)

        root.addWidget(self._armor_panel)

        root.addWidget(_sep())

        heal_btn = QPushButton("Heal to 100")
        heal_btn.clicked.connect(self._heal)
        root.addWidget(heal_btn)

        root.addWidget(_sep())

        self._noise_check = QCheckBox("OCR noise jitter (±2%)")
        self._noise_check.toggled.connect(self._toggle_noise)
        root.addWidget(self._noise_check)

        self._update_armor_mode()

        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def set_damage_session(self, session):
        self._damage_session_ref = session

    def set_armor_session(self, session):
        self._armor_session_ref = session
        if session is not None:
            pen = str(session.base_damage)
            blunt = str(max(1, session.threshold // 2))
            self._auto_pen_dmg.setText(pen)
            self._man_pen_dmg.setText(pen)
            self._auto_blunt_dmg.setText(blunt)
            self._man_blunt_dmg.setText(blunt)

    def _on_slider(self, value: int):
        self._provider.inject_value(value)

    def _shoot_damage(self):
        try:
            dmg = int(self._damage_edit.text())
        except ValueError:
            return
        self._provider.apply_damage(dmg)
        self._sync_slider()

    def _shoot_armor_rng(self):
        pen_chance = self._pen_chance_spin.value() / 100.0
        if random.random() < pen_chance:
            self._apply_dmg_str(self._auto_pen_dmg.text())
        else:
            self._apply_dmg_str(self._auto_blunt_dmg.text())

    def _shoot_armor_pen(self):
        self._apply_dmg_str(self._man_pen_dmg.text())

    def _shoot_armor_blunt(self):
        self._apply_dmg_str(self._man_blunt_dmg.text())

    def _apply_dmg_str(self, text: str):
        try:
            dmg = int(text)
        except ValueError:
            return
        self._provider.apply_damage(dmg)
        self._sync_slider()

    def _heal(self):
        self._provider.inject_value(100)
        self._sync_slider()

    def _toggle_noise(self, checked: bool):
        self._provider.noise_enabled = checked

    def _update_armor_mode(self):
        auto = self._auto_radio.isChecked()
        self._auto_panel.setVisible(auto)
        self._manual_panel.setVisible(not auto)

    def _sync_slider(self):
        self._slider.blockSignals(True)
        self._slider.setValue(self._provider.current_health)
        self._slider.blockSignals(False)

    def _refresh(self):
        hp = self._provider.current_health
        self._slider.blockSignals(True)
        self._slider.setValue(hp)
        self._slider.blockSignals(False)
        self._figure.set_health(hp)
        self._health_label.setText(f"Health: {hp}")

        session = self._armor_session_ref or self._damage_session_ref
        if session is not None:
            state = session.current_state
            self._state_label.setText(f"State: {state.value if hasattr(state, 'value') else state}")
        else:
            self._state_label.setText("State: IDLE")

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
