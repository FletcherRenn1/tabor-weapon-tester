import os

from PyQt6.QtWidgets import (
    QDialog, QWizard, QWizardPage, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QCheckBox, QFileDialog, QWidget, QFrame,
)
from PyQt6.QtCore import Qt

from app.data.config import Config
from app.ui.styles import checkbox_css


_BASE_STYLESHEET = """
QDialog, QWizard, QWizardPage, QWidget { background: #000; color: #fff; font-size: 14px; }
QPushButton {
    background: #111; color: #fff; border: 1px solid #444; padding: 6px 16px;
}
QPushButton:hover { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #222; }
QLineEdit { background: #111; color: #fff; border: 1px solid #444; padding: 5px 10px; }
QFrame[frameShape="4"] { color: #222; }
"""

STYLESHEET = _BASE_STYLESHEET + checkbox_css()


def _sep():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #222;")
    return line


def _h1(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 20px; padding-bottom: 4px;")
    return lbl


def _body(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #aaa; font-size: 13px;")
    return lbl


class SetupWizard(QWizard):
    def __init__(self, config: Config, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(560, 480)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOptions(
            QWizard.WizardOption.NoBackButtonOnStartPage |
            QWizard.WizardOption.NoCancelButton
        )
        self._config = config

        self.addPage(WelcomePage(version))
        self.addPage(SaveLocationPage(config))
        self.addPage(CalibrationPage(config))
        self.addPage(UpdatesPage(config))
        self.addPage(SyncPage(config))
        self.addPage(SummaryPage(config))

        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self._on_finish)

    def _on_finish(self):
        self._config.wizard_complete = True
        self._config.save()


class WelcomePage(QWizardPage):
    def __init__(self, version: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_h1("Tabor Weapon Tester"))
        layout.addWidget(_body(
            f"Version {version}\n\n"
            "This tool monitors the chest health value from your game's streamer cam "
            "and guides you through a 10-shot damage test. It records each shot, "
            "computes statistics, and can optionally share results with the community database.\n\n"
            "This setup runs once. You can change any setting later."
        ))
        layout.addStretch()

    def isComplete(self):
        return True


class SaveLocationPage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        self._config = config
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_h1("Save location"))
        layout.addWidget(_body("Where should test results be saved?"))

        row = QHBoxLayout()
        self._path_edit = QLineEdit(config.save_location)
        row.addWidget(self._path_edit)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)
        layout.addStretch()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select folder", self._path_edit.text())
        if path:
            self._path_edit.setText(path)

    def validatePage(self):
        self._config.save_location = self._path_edit.text()
        os.makedirs(self._config.save_location, exist_ok=True)
        self._config.save()
        return True


class CalibrationPage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_h1("Screen calibration"))
        layout.addWidget(_body(
            "Calibration is done in Settings > Calibration once you have the game running. "
            "You don't need to do it now.\n\n"
            "To test the app without the game, go to Settings > Dev and enable Mock Mode "
            "after this setup finishes."
        ))
        layout.addStretch()

    def isComplete(self):
        return True


class UpdatesPage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        self._config = config

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_h1("Auto-updates"))
        layout.addWidget(_body(
            "The app can check GitHub for new versions on launch. "
            "This is off by default - you can enable it any time in Settings > Updates."
        ))

        layout.addWidget(_sep())

        self._permanent_out = QCheckBox("Permanently opt out")
        self._permanent_out.setStyleSheet("color: #f88;")
        layout.addWidget(self._permanent_out)
        warn = QLabel("The Updates section will not appear anywhere in the app. Cannot be undone without reinstalling.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #a55; font-size: 12px; padding-left: 22px;")
        layout.addWidget(warn)

        layout.addStretch()

    def validatePage(self):
        if self._permanent_out.isChecked():
            self._config.permanent_optout_updates = True
            self._config.updates_enabled = False
            self._config.updates_opted_in = False
        self._config.save()
        return True


class SyncPage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        self._config = config

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_h1("Community database"))
        layout.addWidget(_body(
            "Completed tests can be uploaded to the community database so others can see your results. "
            "This is off by default - you can enable it any time in Settings > Site sync."
        ))

        layout.addWidget(_sep())

        self._permanent_out = QCheckBox("Permanently opt out")
        self._permanent_out.setStyleSheet("color: #f88;")
        layout.addWidget(self._permanent_out)
        warn = QLabel("The Site sync section will not appear anywhere in the app. Cannot be undone without reinstalling.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #a55; font-size: 12px; padding-left: 22px;")
        layout.addWidget(warn)

        layout.addStretch()

    def validatePage(self):
        if self._permanent_out.isChecked():
            self._config.permanent_optout_sync = True
            self._config.sync_enabled = False
            self._config.sync_opted_in = False
        self._config.save()
        return True


class SummaryPage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        self._config = config

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_h1("Setup complete"))

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color: #aaa; font-size: 13px;")
        layout.addWidget(self._summary)
        layout.addStretch()

    def initializePage(self):
        c = self._config
        lines = [
            f"Save location:  {c.save_location}",
            f"Calibration:    set up in Settings when game is running",
        ]
        if c.permanent_optout_updates:
            lines.append("Updates:        Permanently opted out")
        else:
            lines.append("Updates:        Off  (enable in Settings > Updates)")

        if c.permanent_optout_sync:
            lines.append("Site sync:      Permanently opted out")
        else:
            lines.append("Site sync:      Off  (enable in Settings > Site sync)")

        self._summary.setText("\n".join(lines))

    def isComplete(self):
        return True
