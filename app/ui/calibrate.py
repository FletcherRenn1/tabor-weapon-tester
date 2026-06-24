import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QCursor

from app.core.capture import ScreenCapture, list_monitors
from app.core.ocr import HealthReader


STYLESHEET = """
QWidget { background: #000; color: #fff; font-size: 13px; }
QPushButton { background: #111; color: #fff; border: 1px solid #444; padding: 6px 14px; }
QPushButton:hover { background: #1a1a1a; }
QPushButton:disabled { color: #555; border-color: #333; }
QLineEdit { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
QScrollArea { border: none; }
"""


class MonitorPicker(QDialog):
    monitor_chosen = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select monitor")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select the monitor where the game is running:"))
        layout.addSpacing(10)

        monitors = list_monitors()
        row = QHBoxLayout()
        row.setSpacing(12)

        for m in monitors:
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(6)
            card_layout.setContentsMargins(0, 0, 0, 0)

            thumb_label = QLabel()
            thumb_label.setFixedSize(240, 135)
            thumb_label.setStyleSheet("background: #111; border: 1px solid #333;")
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            try:
                cap = ScreenCapture(m["index"], 0, 0, m["width"], m["height"])
                img = cap.grab_full_monitor()
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                thumb = cv2.resize(rgb, (240, int(240 * h / w)))
                th, tw = thumb.shape[:2]
                qimg = QImage(bytes(thumb.data), tw, th, 3 * tw, QImage.Format.Format_RGB888)
                thumb_label.setPixmap(QPixmap.fromImage(qimg))
            except Exception:
                thumb_label.setText(f"{m['width']}x{m['height']}")

            card_layout.addWidget(thumb_label)
            btn = QPushButton(f"Monitor {m['index'] + 1}  —  {m['width']}x{m['height']}")
            btn.clicked.connect(lambda checked, info=m: self._pick(info))
            card_layout.addWidget(btn)
            row.addWidget(card)

        layout.addLayout(row)
        layout.addSpacing(10)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def _pick(self, info: dict):
        self.monitor_chosen.emit(info)
        self.accept()


class CapturePrompt(QDialog):
    confirmed = pyqtSignal()

    def __init__(self, monitor_info: dict, parent=None):
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Capture screenshot")
        self.setStyleSheet(STYLESHEET)
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        msg = QLabel(
            f"Switch to Monitor {monitor_info['index'] + 1} "
            f"({monitor_info['width']}x{monitor_info['height']}) and get the game visible, "
            f"then click Capture."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btns = QHBoxLayout()
        capture_btn = QPushButton("Capture")
        capture_btn.clicked.connect(self._on_capture)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(capture_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _on_capture(self):
        self.accept()
        QTimer.singleShot(0, self.confirmed.emit)


class ScreenshotCanvas(QLabel):
    selection_changed = pyqtSignal(QRect)

    def __init__(self, pixmap: QPixmap):
        super().__init__()
        self._base = pixmap
        self._sel = QRect()
        self._dragging = False
        self._origin = QPoint()
        self.setPixmap(pixmap)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.pos()
            self._sel = QRect(self._origin, QSize())
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._sel = QRect(self._origin, event.pos()).normalized()
            self.update()
            self.selection_changed.emit(self._sel)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._sel = QRect(self._origin, event.pos()).normalized()
            self.update()
            self.selection_changed.emit(self._sel)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._sel.isNull() and self._sel.width() > 2:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(self._sel)
            painter.fillRect(self._sel, QColor(255, 255, 255, 30))

    def selection(self) -> QRect:
        return self._sel


class CropDialog(QDialog):
    crop_confirmed = pyqtSignal(int, int, int, int)

    def __init__(self, screenshot: np.ndarray, monitor_info: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select region")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(800, 560)
        self._monitor_info = monitor_info
        self._screenshot = screenshot
        self._ocr_timer = None
        self._reader = None

        sh, sw = screenshot.shape[:2]
        self._img_w = sw
        self._img_h = sh

        rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
        qimg = QImage(bytes(rgb.data), sw, sh, 3 * sw, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        instr = QLabel("Click and drag to select the chest health value area.")
        instr.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(instr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        self._canvas = ScreenshotCanvas(self._pixmap)
        self._canvas.selection_changed.connect(self._on_selection)
        scroll.setWidget(self._canvas)
        layout.addWidget(scroll, stretch=1)

        bottom = QHBoxLayout()
        self._ocr_label = QLabel("OCR: drag to select a region")
        self._ocr_label.setStyleSheet("color: #888; font-size: 12px;")
        bottom.addWidget(self._ocr_label)
        bottom.addStretch()
        self._confirm_btn = QPushButton("Confirm")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(self._confirm_btn)
        bottom.addWidget(cancel_btn)
        layout.addLayout(bottom)

    def _on_selection(self, rect: QRect):
        self._confirm_btn.setEnabled(rect.width() > 5 and rect.height() > 5)
        self._start_ocr(rect)

    def _start_ocr(self, rect: QRect):
        if self._ocr_timer:
            self._ocr_timer.stop()
        mw = self._monitor_info["width"]
        mh = self._monitor_info["height"]
        scale_x = self._img_w / mw
        scale_y = self._img_h / mh
        x = int(rect.x() / scale_x) if scale_x else rect.x()
        y = int(rect.y() / scale_y) if scale_y else rect.y()
        w = max(1, int(rect.width() / scale_x)) if scale_x else rect.width()
        h = max(1, int(rect.height() / scale_y)) if scale_y else rect.height()
        try:
            cap = ScreenCapture(self._monitor_info["index"], x, y, w, h)
            self._reader = HealthReader(cap)
        except Exception:
            self._reader = None
            return
        self._ocr_timer = QTimer()
        self._ocr_timer.setInterval(500)
        self._ocr_timer.timeout.connect(self._update_ocr)
        self._ocr_timer.start()

    def _update_ocr(self):
        if self._reader is None:
            return
        val = self._reader.read()
        if val is None:
            self._ocr_label.setText("OCR: no reading")
        else:
            self._ocr_label.setText(f"OCR: {val}%")

    def _confirm(self):
        rect = self._canvas.selection()
        if rect.isNull() or rect.width() < 5:
            return
        if self._ocr_timer:
            self._ocr_timer.stop()
        mw = self._monitor_info["width"]
        mh = self._monitor_info["height"]
        scale_x = self._img_w / mw
        scale_y = self._img_h / mh
        x = int(rect.x() / scale_x) if scale_x else rect.x()
        y = int(rect.y() / scale_y) if scale_y else rect.y()
        w = max(1, int(rect.width() / scale_x)) if scale_x else rect.width()
        h = max(1, int(rect.height() / scale_y)) if scale_y else rect.height()
        self.crop_confirmed.emit(x, y, w, h)
        self.accept()

    def closeEvent(self, event):
        if self._ocr_timer:
            self._ocr_timer.stop()
        super().closeEvent(event)


class ProfileNameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Name this profile")
        self.setStyleSheet(STYLESHEET)
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Profile name:"))
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("e.g. 1080p main")
        layout.addWidget(self._edit)
        layout.addSpacing(8)

        btns = QHBoxLayout()
        ok = QPushButton("Save")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def profile_name(self) -> str:
        return self._edit.text().strip()


class CalibrationFlow:
    def __init__(self, parent_widget, config, callback):
        self._parent = parent_widget
        self._config = config
        self._callback = callback
        self._monitor_info = None
        self._prompt = None
        self._crop_dialog = None

    def start(self):
        picker = MonitorPicker(self._parent)
        picker.monitor_chosen.connect(self._on_monitor)
        picker.exec()

    def _on_monitor(self, monitor_info):
        self._monitor_info = monitor_info
        self._prompt = CapturePrompt(monitor_info, self._parent)
        self._prompt.confirmed.connect(self._on_capture_confirmed)
        self._prompt.exec()

    def _on_capture_confirmed(self):
        try:
            cap = ScreenCapture(
                self._monitor_info["index"], 0, 0,
                self._monitor_info["width"], self._monitor_info["height"],
            )
            screenshot = cap.grab_full_monitor()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self._parent, "Capture failed", str(e))
            return

        self._crop_dialog = CropDialog(screenshot, self._monitor_info, self._parent)
        self._crop_dialog.crop_confirmed.connect(self._on_crop)
        self._crop_dialog.exec()

    def _on_crop(self, x, y, w, h):
        name_dlg = ProfileNameDialog(self._parent)
        if name_dlg.exec() == QDialog.DialogCode.Accepted:
            name = name_dlg.profile_name()
            if not name:
                name = f"Profile {len(self._config.calibration_profiles) + 1}"
            self._config.calibration_profiles[name] = {
                "monitor_index": self._monitor_info["index"],
                "x": x, "y": y, "w": w, "h": h,
            }
            self._config.active_profile = name
            self._config.save()
            self._callback(name)


def run_calibration_flow(parent_widget, config, callback):
    flow = CalibrationFlow(parent_widget, config, callback)
    parent_widget._active_calibration_flow = flow
    flow.start()
