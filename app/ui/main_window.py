from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QMessageBox, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot

from app.data.config import Config
from app.core.session import Session, State
from app.core.tts import TTSEngine
from app.core.mock import MockHealthProvider
from app.core.capture import ScreenCapture, list_monitors
from app.core.ocr import HealthReader
from app.core.updater import Updater
from app.core.sync import SyncClient
from app.data.storage import save_result, HP_PER_PERCENT
from app.ui.settings import SettingsDialog
from app.ui.results import ResultsBrowser
from app.ui.simulator import SimulatorWindow


STYLESHEET = """
QMainWindow, QWidget { background: #000; color: #fff; font-size: 14px; }
QPushButton {
    background: #111; color: #fff; border: 1px solid #444; padding: 8px 18px;
}
QPushButton:hover { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #222; }
QLineEdit { background: #111; color: #fff; border: 1px solid #444; padding: 6px 10px; }
QLabel#banner { background: #1a1a00; color: #ffff88; padding: 6px 10px; border-bottom: 1px solid #444; }
QLabel#status { font-size: 20px; padding: 10px 0 4px 0; }
QLabel#sub { color: #888; font-size: 13px; }
QFrame#sep { color: #222; }
"""

_PAGE_IDLE    = 0
_PAGE_ARMED   = 1
_PAGE_TESTING = 2


def _sep():
    line = QFrame()
    line.setObjectName("sep")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


class MainWindow(QMainWindow):
    def __init__(self, config: Config, version: str):
        super().__init__()
        self.setWindowTitle("Tabor Weapon Tester")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(500, 420)
        self._config = config
        self._version = version
        self._session: Session | None = None
        self._mock_provider: MockHealthProvider | None = None
        self._sim_window: SimulatorWindow | None = None
        self._tts = TTSEngine(config)
        self._settings_dlg: SettingsDialog | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        self._banner = QLabel()
        self._banner.setObjectName("banner")
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setCursor(Qt.CursorShape.PointingHandCursor)
        self._banner.mousePressEvent = self._on_banner_click
        self._banner.hide()
        root.addWidget(self._banner)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 16, 24, 16)
        body_layout.setSpacing(10)
        root.addWidget(body)

        top_row = QHBoxLayout()
        self._profile_label = QLabel()
        self._profile_label.setStyleSheet("color: #666; font-size: 12px;")
        top_row.addWidget(self._profile_label)
        top_row.addStretch()
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._open_settings)
        top_row.addWidget(settings_btn)
        results_btn = QPushButton("Results")
        results_btn.clicked.connect(self._open_results)
        top_row.addWidget(results_btn)
        body_layout.addLayout(top_row)
        body_layout.addWidget(_sep())

        self._status_label = QLabel("")
        self._status_label.setObjectName("status")
        body_layout.addWidget(self._status_label)

        self._health_label = QLabel("")
        self._health_label.setObjectName("sub")
        body_layout.addWidget(self._health_label)

        self._shots_label = QLabel("")
        self._shots_label.setObjectName("sub")
        body_layout.addWidget(self._shots_label)

        body_layout.addStretch()
        body_layout.addWidget(_sep())

        self._stack = QStackedWidget()
        body_layout.addWidget(self._stack)

        self._stack.addWidget(self._build_idle_page())
        self._stack.addWidget(self._build_armed_page())
        self._stack.addWidget(self._build_testing_page())
        self._stack.setCurrentIndex(_PAGE_IDLE)

        self._update_profile_label()
        self._refresh_idle_status()

        if not config.permanent_optout_updates and config.updates_enabled:
            QTimer.singleShot(2000, self._check_updates)

    def _build_idle_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)
        self._ready_btn = QPushButton("Ready for test")
        self._ready_btn.clicked.connect(self._go_armed)
        layout.addWidget(self._ready_btn)
        return page

    def _build_armed_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Weapon:"))
        self._weapon_edit = QLineEdit()
        self._weapon_edit.setPlaceholderText("e.g. AK-74")
        layout.addWidget(self._weapon_edit)

        layout.addWidget(QLabel("Caliber:"))
        self._caliber_edit = QLineEdit()
        self._caliber_edit.setPlaceholderText("e.g. 5.45x39")
        layout.addWidget(self._caliber_edit)

        btns = QHBoxLayout()
        self._start_btn = QPushButton("Start test")
        self._start_btn.clicked.connect(self._start)
        btns.addWidget(self._start_btn)
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._go_idle)
        btns.addWidget(back_btn)
        layout.addLayout(btns)

        return page

    def _build_testing_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        btns = QHBoxLayout()
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.clicked.connect(self._pause)
        btns.addWidget(self._pause_btn)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        btns.addWidget(self._cancel_btn)
        layout.addLayout(btns)

        return page

    def _go_idle(self):
        self._weapon_edit.clear()
        self._caliber_edit.clear()
        self._health_label.setText("")
        self._shots_label.setText("")
        self._stack.setCurrentIndex(_PAGE_IDLE)
        self._refresh_idle_status()

    def _go_armed(self):
        if not self._config.active_profile and not self._config.mock_mode:
            QMessageBox.warning(self, "No calibration", "Set up a calibration profile in Settings first.")
            return
        self._status_label.setText("Enter weapon details")
        self._stack.setCurrentIndex(_PAGE_ARMED)
        self._weapon_edit.setFocus()

    def _update_profile_label(self):
        name = self._config.active_profile or "(no profile)"
        self._profile_label.setText(f"Profile: {name}")

    def _refresh_idle_status(self):
        if self._config.mock_mode:
            self._status_label.setText("Status: OK")
            self._ready_btn.setEnabled(True)
            return

        profile_name = self._config.active_profile
        if not profile_name:
            profiles = self._config.calibration_profiles
            if not profiles:
                self._status_label.setText("Status: Not OK:no calibration profiles (Settings > Calibration)")
            else:
                self._status_label.setText("Status: Not OK:no active profile selected (Settings > Calibration)")
            self._ready_btn.setEnabled(False)
            return

        prof_data = self._config.calibration_profiles.get(profile_name)
        if not prof_data:
            self._status_label.setText("Status: Not OK:active profile data missing, recalibrate")
            self._ready_btn.setEnabled(False)
            return

        monitors = list_monitors()
        if not any(m["index"] == prof_data["monitor_index"] for m in monitors):
            self._status_label.setText("Status: Not OK:monitor not found, recalibrate in Settings")
            self._ready_btn.setEnabled(False)
            return

        self._status_label.setText("Status: OK")
        self._ready_btn.setEnabled(True)

    def _build_provider(self):
        if self._config.mock_mode:
            if self._mock_provider is None:
                self._mock_provider = MockHealthProvider()
            return self._mock_provider
        profile = self._config.active_profile
        if not profile or profile not in self._config.calibration_profiles:
            return None
        prof = self._config.calibration_profiles[profile]
        capture = ScreenCapture(prof["monitor_index"], prof["x"], prof["y"], prof["w"], prof["h"])
        return HealthReader(capture)

    def _start(self):
        provider = self._build_provider()
        if provider is None:
            QMessageBox.warning(self, "No provider", "Could not create health reader. Check calibration.")
            return
        weapon = self._weapon_edit.text().strip()
        if not weapon:
            QMessageBox.warning(self, "Missing info", "Enter a weapon name.")
            self._weapon_edit.setFocus()
            return

        caliber = self._caliber_edit.text().strip()

        self._session = Session(provider, self._config)
        self._session.state_changed.connect(self._on_state_changed)
        self._session.shot_recorded.connect(self._on_shot_recorded)
        self._session.health_updated.connect(self._on_health_updated)
        self._session.test_complete.connect(self._on_complete)

        self._shots_label.setText("Shots: 0 / 10")
        self._stack.setCurrentIndex(_PAGE_TESTING)
        self._session.start(weapon, caliber)

    def _pause(self):
        if self._session is None:
            return
        if self._session.current_state == State.PAUSED:
            self._session.resume()
            self._pause_btn.setText("Pause")
        else:
            self._session.pause()
            self._pause_btn.setText("Resume")

    def _cancel(self):
        reply = QMessageBox.question(
            self, "Cancel test",
            "Cancel? All recorded shots will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._session:
                self._session.cancel()
                self._session = None
            self._pause_btn.setText("Pause")
            self._go_idle()

    @pyqtSlot(str)
    def _on_state_changed(self, state_name: str):
        messages = {
            "WAITING_FOR_FULL_HEALTH": "Waiting — heal to 100%",
            "READY_TO_SHOOT": "Shoot now",
            "WAITING_FOR_HIT": "Tracking hit...",
            "RECORDING_VALUE": "Recording...",
            "HEAL_WARNING": "Heal up before next shot",
            "PAUSED": "Paused — heal to 100% to resume",
            "COMPLETE": "Test complete",
        }
        self._status_label.setText(messages.get(state_name, state_name))

        if state_name == "READY_TO_SHOOT":
            self._tts.speak_event("shoot")
        elif state_name == "HEAL_WARNING":
            self._tts.speak_event("heal")
        elif state_name == "COMPLETE":
            self._tts.speak_event("complete")

    @pyqtSlot(int, int)
    def _on_shot_recorded(self, shot_num: int, damage: int):
        hp = damage * HP_PER_PERCENT
        self._shots_label.setText(f"Shots: {shot_num} / 10:last: {damage}% ({hp} HP)")
        self._tts.speak_event("recorded", damage=damage, hp=hp)

    @pyqtSlot(int)
    def _on_health_updated(self, health: int):
        hp = health * HP_PER_PERCENT
        self._health_label.setText(f"Health: {health}% ({hp} HP)")

    @pyqtSlot(dict)
    def _on_complete(self, results: dict):
        shots = results["shots"]
        avg = results["avg"]
        min_val = results["min_val"]
        max_val = results["max_val"]
        stddev = results["stddev"]

        avg_hp = round(avg * HP_PER_PERCENT, 1)
        lines = [
            f"Average: {avg:.1f}% ({avg_hp} HP)"
            f"  Min: {min_val}% ({min_val * HP_PER_PERCENT} HP)"
            f"  Max: {max_val}% ({max_val * HP_PER_PERCENT} HP)"
            f"  StdDev: {stddev:.1f}% ({round(stddev * HP_PER_PERCENT, 1)} HP)",
            "",
        ]
        for i, dmg in enumerate(shots, 1):
            lines.append(f"Shot {i}: {dmg}% ({dmg * HP_PER_PERCENT} HP)")

        reply = QMessageBox.question(
            self, "Test complete",
            "\n".join(lines) + "\n\nSave to file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            path = save_result(results["weapon"], results["caliber"], shots, avg, min_val, max_val, stddev)
            QMessageBox.information(self, "Saved", f"Saved to:\n{path}")

        if not self._config.permanent_optout_sync and self._config.sync_enabled:
            sync_reply = QMessageBox.question(
                self, "Upload results", "Upload to community database?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if sync_reply == QMessageBox.StandardButton.Yes:
                ok = SyncClient(self._config, self._version).submit(results)
                if not ok:
                    QMessageBox.warning(self, "Upload failed", "Could not upload results.")

        self._session = None
        self._pause_btn.setText("Pause")
        self._go_idle()

    def _check_updates(self):
        result = Updater(self._version, self._config).check()
        if result:
            self._banner.setText(f"Update available: v{result['version']}:click here")
            self._banner.show()
            self._tts.speak_event("update")

    def _on_banner_click(self, event):
        self._open_settings()
        if self._settings_dlg:
            self._settings_dlg.go_to_updates_tab()

    def _open_settings(self):
        dlg = SettingsDialog(self._config, self._tts, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.open_simulator.connect(self._open_simulator)
        self._settings_dlg = dlg
        dlg.exec()
        self._settings_dlg = None

    def _on_settings_changed(self):
        self._update_profile_label()
        self._refresh_idle_status()

    def _open_simulator(self):
        if not self._config.mock_mode:
            return
        if self._mock_provider is None:
            self._mock_provider = MockHealthProvider()
        if self._sim_window is None or not self._sim_window.isVisible():
            self._sim_window = SimulatorWindow(self._mock_provider, self._session)
            self._sim_window.show()
        else:
            self._sim_window.raise_()

    def _open_results(self):
        dlg = QMainWindow(self)
        dlg.setWindowTitle("Results browser")
        dlg.setStyleSheet(STYLESHEET)
        dlg.setMinimumSize(800, 500)
        dlg.setCentralWidget(ResultsBrowser(self._config))
        dlg.show()
