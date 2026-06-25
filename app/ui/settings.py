import hashlib

from app.ui.styles import checkbox_css
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QCheckBox, QSlider, QComboBox, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QSpinBox, QRadioButton,
    QButtonGroup, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from app.data.config import Config
from app.core.tts import TTSEngine
from app.ui.calibrate import run_calibration_flow
from app.data.dev_auth import DEV_HASH


def _check_password(password: str) -> bool:
    if not DEV_HASH:
        return False
    try:
        _, algo, iterations, salt, expected = DEV_HASH.split(":")
        dk = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), int(iterations))
        return dk.hex() == expected
    except Exception:
        return False


_dev_unlocked = False


_BASE_STYLESHEET = """
QDialog, QWidget { background: #000; color: #fff; font-size: 13px; }
QTabWidget::pane { border: 1px solid #333; background: #000; }
QTabBar::tab { background: #111; color: #888; padding: 8px 16px; border: 1px solid #333; }
QTabBar::tab:selected { background: #000; color: #fff; border-bottom: none; }
QPushButton { background: #111; color: #fff; border: 1px solid #444; padding: 5px 12px; }
QPushButton:hover { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #222; }
QLineEdit { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
QSlider::groove:horizontal { background: #333; height: 4px; }
QSlider::handle:horizontal { background: #fff; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QComboBox { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; min-width: 160px; }
QListWidget { background: #0a0a0a; border: 1px solid #333; }
QListWidget::item { padding: 5px 8px; }
QListWidget::item:selected { background: #1a1a1a; }
QSpinBox { background: #111; color: #fff; border: 1px solid #444; padding: 4px 8px; }
"""

STYLESHEET = _BASE_STYLESHEET + checkbox_css()

def _sep():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #222;")
    return line


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal()
    open_simulator = pyqtSignal()

    def __init__(self, config: Config, tts_engine: TTSEngine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(560, 520)
        self._config = config
        self._tts = tts_engine
        self._sim_window = None

        root = QVBoxLayout(self)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._build_general()
        self._build_calibration()
        self._build_tts()
        if not config.permanent_optout_updates:
            self._build_updates()
        if not config.permanent_optout_sync:
            self._build_sync()
        self._build_dev()

        self._tabs.currentChanged.connect(self._on_tab_changed)

        bottom = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #8f8; font-size: 12px;")
        bottom.addWidget(self._status_label)
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

        self._status_timer = QTimer()
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self._status_label.setText(""))

    def _build_general(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        layout.addWidget(QLabel("File save location:"))
        row = QHBoxLayout()
        self._save_location = QLineEdit(self._config.save_location)
        row.addWidget(self._save_location)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_save)
        row.addWidget(browse)
        layout.addLayout(row)

        layout.addWidget(_sep())
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Safety buffer (%):"))
        self._safety_spin = QSpinBox()
        self._safety_spin.setRange(0, 50)
        self._safety_spin.setValue(self._config.safety_buffer)
        row2.addWidget(self._safety_spin)
        row2.addStretch()
        layout.addLayout(row2)

        layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_general)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._tabs.addTab(tab, "General")

    def _browse_save(self):
        path = QFileDialog.getExistingDirectory(self, "Select save folder", self._config.save_location)
        if path:
            self._save_location.setText(path)

    def _save_general(self):
        self._config.save_location = self._save_location.text()
        self._config.safety_buffer = self._safety_spin.value()
        self._config.save()
        self.settings_changed.emit()
        self._show_saved()

    def _build_calibration(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self._profile_list = QListWidget()
        layout.addWidget(self._profile_list)
        self._refresh_profile_list()

        btn_row = QHBoxLayout()
        new_btn = QPushButton("New profile")
        new_btn.clicked.connect(self._new_profile)
        btn_row.addWidget(new_btn)

        self._recal_btn = QPushButton("Recalibrate selected")
        self._recal_btn.clicked.connect(self._recalibrate)
        btn_row.addWidget(self._recal_btn)

        self._del_btn = QPushButton("Delete selected")
        self._del_btn.clicked.connect(self._delete_profile)
        btn_row.addWidget(self._del_btn)

        layout.addLayout(btn_row)

        activate_btn = QPushButton("Set selected as active")
        activate_btn.clicked.connect(self._set_active)
        layout.addWidget(activate_btn)

        self._tabs.addTab(tab, "Calibration")

    def _refresh_profile_list(self):
        self._profile_list.clear()
        for name in self._config.calibration_profiles:
            marker = " [active]" if name == self._config.active_profile else ""
            self._profile_list.addItem(name + marker)

    def _new_profile(self):
        run_calibration_flow(self, self._config, self._on_profile_saved)

    def _recalibrate(self):
        item = self._profile_list.currentItem()
        if not item:
            return
        name = item.text().replace(" [active]", "").strip()
        run_calibration_flow(self, self._config, self._on_profile_saved)

    def _delete_profile(self):
        item = self._profile_list.currentItem()
        if not item:
            return
        name = item.text().replace(" [active]", "").strip()
        if name in self._config.calibration_profiles:
            del self._config.calibration_profiles[name]
            if self._config.active_profile == name:
                self._config.active_profile = ""
            self._config.save()
            self._refresh_profile_list()
            self.settings_changed.emit()

    def _set_active(self):
        item = self._profile_list.currentItem()
        if not item:
            return
        name = item.text().replace(" [active]", "").strip()
        if name in self._config.calibration_profiles:
            self._config.active_profile = name
            self._config.save()
            self._refresh_profile_list()
            self.settings_changed.emit()

    def _on_profile_saved(self, name: str):
        self._refresh_profile_list()
        self.settings_changed.emit()

    def _build_tts(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self._tts_enabled = QCheckBox("Enable TTS")
        self._tts_enabled.setChecked(self._config.tts_enabled)
        layout.addWidget(self._tts_enabled)

        layout.addWidget(_sep())
        layout.addWidget(QLabel("Volume:"))
        self._tts_volume = QSlider(Qt.Orientation.Horizontal)
        self._tts_volume.setRange(0, 100)
        self._tts_volume.setValue(int(self._config.tts_volume * 100))
        layout.addWidget(self._tts_volume)

        layout.addWidget(_sep())
        layout.addWidget(QLabel("Voice:"))
        self._tts_voice = QComboBox()
        voices = self._tts.get_available_voices()
        for v in voices:
            self._tts_voice.addItem(v["name"], v["id"])
        current = self._config.tts_voice
        for i, v in enumerate(voices):
            if v["id"] == current:
                self._tts_voice.setCurrentIndex(i)
                break
        layout.addWidget(self._tts_voice)

        layout.addWidget(_sep())
        layout.addWidget(QLabel("Events:"))
        events = {
            "ready": "Health reached 100 / ready",
            "shoot": "Shoot now prompt",
            "recorded": "Value recorded",
            "heal": "Heal warning",
            "complete": "Test complete",
            "update": "Update available",
        }
        self._tts_event_checks = {}
        tts_events = self._config.tts_events
        for key, label in events.items():
            cb = QCheckBox(label)
            cb.setChecked(tts_events.get(key, True))
            layout.addWidget(cb)
            self._tts_event_checks[key] = cb
            if key == "recorded":
                self._tts_recorded_hp = QCheckBox("  Include HP in shot announcement")
                self._tts_recorded_hp.setStyleSheet("color: #aaa; padding-left: 12px;")
                self._tts_recorded_hp.setChecked(tts_events.get("recorded_hp", True))
                cb.toggled.connect(self._tts_recorded_hp.setEnabled)
                self._tts_recorded_hp.setEnabled(cb.isChecked())
                layout.addWidget(self._tts_recorded_hp)
                self._tts_event_checks["recorded_hp"] = self._tts_recorded_hp

        layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_tts)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._tabs.addTab(tab, "TTS")

    def _save_tts(self):
        self._config.tts_enabled = self._tts_enabled.isChecked()
        self._config.tts_volume = self._tts_volume.value() / 100.0
        if self._tts_voice.currentData():
            self._config.tts_voice = self._tts_voice.currentData()
        for key, cb in self._tts_event_checks.items():
            self._config.tts_events[key] = cb.isChecked()
        self._config.save()
        self._tts.reload_config()
        self.settings_changed.emit()
        self._show_saved()

    def _build_updates(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self._updates_enabled = QCheckBox("Check for updates on launch")
        self._updates_enabled.setChecked(self._config.updates_enabled)
        layout.addWidget(self._updates_enabled)

        layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_updates)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._tabs.addTab(tab, "Updates")

    def _save_updates(self):
        self._config.updates_enabled = self._updates_enabled.isChecked()
        self._config.updates_opted_in = True
        self._config.save()
        self.settings_changed.emit()
        self._show_saved()

    def _build_sync(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self._sync_enabled = QCheckBox("Upload results to community database")
        self._sync_enabled.setChecked(self._config.sync_enabled)
        layout.addWidget(self._sync_enabled)

        layout.addWidget(QLabel("Username (leave blank for anonymous):"))
        self._sync_username = QLineEdit(self._config.sync_username)
        layout.addWidget(self._sync_username)

        layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_sync)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._tabs.addTab(tab, "Site sync")

    def _save_sync(self):
        self._config.sync_enabled = self._sync_enabled.isChecked()
        self._config.sync_username = self._sync_username.text().strip()
        self._config.sync_opted_in = True
        self._config.save()
        self.settings_changed.emit()
        self._show_saved()

    def _build_dev(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._dev_stack = QStackedWidget()
        outer.addWidget(self._dev_stack)

        locked = QWidget()
        locked_layout = QVBoxLayout(locked)
        locked_layout.setContentsMargins(20, 20, 20, 20)
        locked_layout.setSpacing(10)
        locked_layout.addWidget(QLabel("Dev access is password protected."))
        self._dev_password_edit = QLineEdit()
        self._dev_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._dev_password_edit.setPlaceholderText("Password")
        self._dev_password_edit.returnPressed.connect(self._attempt_dev_unlock)
        locked_layout.addWidget(self._dev_password_edit)
        unlock_btn = QPushButton("Unlock")
        unlock_btn.clicked.connect(self._attempt_dev_unlock)
        locked_layout.addWidget(unlock_btn)
        self._dev_error = QLabel("")
        self._dev_error.setStyleSheet("color: #f66;")
        locked_layout.addWidget(self._dev_error)
        locked_layout.addStretch()

        unlocked = QWidget()
        unlocked_layout = QVBoxLayout(unlocked)
        unlocked_layout.setContentsMargins(20, 20, 20, 20)
        unlocked_layout.setSpacing(8)
        self._mock_toggle = QCheckBox("Mock mode (bypass OCR for testing)")
        self._mock_toggle.setChecked(self._config.mock_mode)
        unlocked_layout.addWidget(self._mock_toggle)
        self._sim_btn = QPushButton("Open simulator window")
        self._sim_btn.setEnabled(self._config.mock_mode)
        self._mock_toggle.toggled.connect(self._sim_btn.setEnabled)
        self._sim_btn.clicked.connect(self._open_simulator)
        unlocked_layout.addWidget(self._sim_btn)
        unlocked_layout.addWidget(_sep())
        clear_btn = QPushButton("Clear all local results")
        clear_btn.clicked.connect(self._clear_results)
        unlocked_layout.addWidget(clear_btn)
        unlocked_layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_dev)
        unlocked_layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._dev_stack.addWidget(locked)
        self._dev_stack.addWidget(unlocked)
        self._dev_stack.setCurrentIndex(1 if _dev_unlocked else 0)

        self._tabs.addTab(tab, "Dev")

    def _show_saved(self):
        self._status_label.setText("Saved")
        self._status_timer.start(2000)

    def _on_tab_changed(self, index: int):
        pass

    def _attempt_dev_unlock(self):
        global _dev_unlocked
        if _check_password(self._dev_password_edit.text()):
            _dev_unlocked = True
            self._dev_stack.setCurrentIndex(1)
            self._dev_error.setText("")
        else:
            self._dev_error.setText("Incorrect password.")
            self._dev_password_edit.clear()

    def _save_dev(self):
        self._config.mock_mode = self._mock_toggle.isChecked()
        self._config.save()
        self.settings_changed.emit()
        self._show_saved()

    def _open_simulator(self):
        self.open_simulator.emit()

    def _clear_results(self):
        reply = QMessageBox.question(
            self, "Clear results",
            "Delete all locally saved results? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from app.data.storage import delete_all_results
            delete_all_results()

    def go_to_updates_tab(self):
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == "Updates":
                self._tabs.setCurrentIndex(i)
                break
