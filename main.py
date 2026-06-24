import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from app.data.config import Config
from app.ui.wizard import SetupWizard
from app.ui.main_window import MainWindow


def _resource(rel: str) -> str:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)
    return os.path.join(base, rel)


def _read_version() -> str:
    try:
        with open(_resource("VERSION")) as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def main():
    app = QApplication(sys.argv)

    app.setFont(QFont("Segoe UI", 10))

    config = Config.load()
    version = _read_version()

    if not config.wizard_complete:
        wizard = SetupWizard(config, version)
        if wizard.exec() != SetupWizard.DialogCode.Accepted:
            sys.exit(0)
        config = Config.load()

    window = MainWindow(config, version)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
