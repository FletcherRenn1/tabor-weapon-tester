import os
import sys


def _asset_root() -> str:
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def checkbox_css() -> str:
    path = os.path.join(_asset_root(), 'assets', 'ui', 'check.svg').replace('\\', '/')
    return (
        "QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #555; background: #111; }\n"
        f"QCheckBox::indicator:checked {{ background: #1a1a1a; border-color: #888; image: url({path}); }}\n"
        "QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid #555; border-radius: 7px; background: #111; }\n"
        "QRadioButton::indicator:checked { background: #fff; }\n"
    )
