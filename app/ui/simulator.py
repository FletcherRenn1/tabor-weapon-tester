from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLineEdit, QCheckBox, QComboBox, QFrame,
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
        text = f"{self._health}%"
        painter.drawText(0, 65, w, 30, Qt.AlignmentFlag.AlignCenter, text)


class SimulatorWindow(QWidget):
    def __init__(self, provider: MockHealthProvider, session_ref=None):
        super().__init__(None, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Simulator")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumWidth(300)
        self._provider = provider
        self._session_ref = session_ref

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

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #333;")
        root.addWidget(sep1)

        root.addWidget(QLabel("Health:"))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(100)
        self._slider.valueChanged.connect(self._on_slider)
        root.addWidget(self._slider)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #333;")
        root.addWidget(sep2)

        root.addWidget(QLabel("Damage amount:"))
        self._damage_edit = QLineEdit("30")
        root.addWidget(self._damage_edit)

        shoot_btn = QPushButton("Shoot")
        shoot_btn.clicked.connect(self._shoot)
        root.addWidget(shoot_btn)

        heal_btn = QPushButton("Heal to 100")
        heal_btn.clicked.connect(self._heal)
        root.addWidget(heal_btn)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #333;")
        root.addWidget(sep3)

        self._noise_check = QCheckBox("OCR noise jitter (±2%)")
        self._noise_check.toggled.connect(self._toggle_noise)
        root.addWidget(self._noise_check)

        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _on_slider(self, value: int):
        self._provider.inject_value(value)

    def _shoot(self):
        try:
            dmg = int(self._damage_edit.text())
        except ValueError:
            return
        self._provider.apply_damage(dmg)
        self._slider.blockSignals(True)
        self._slider.setValue(self._provider.current_health)
        self._slider.blockSignals(False)

    def _heal(self):
        self._provider.inject_value(100)
        self._slider.blockSignals(True)
        self._slider.setValue(100)
        self._slider.blockSignals(False)

    def _toggle_noise(self, checked: bool):
        self._provider.noise_enabled = checked

    def _refresh(self):
        hp = self._provider.current_health
        self._slider.blockSignals(True)
        self._slider.setValue(hp)
        self._slider.blockSignals(False)
        self._figure.set_health(hp)
        self._health_label.setText(f"Health: {hp}")
        if self._session_ref is not None:
            state = self._session_ref.current_state
            self._state_label.setText(f"State: {state}")

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
