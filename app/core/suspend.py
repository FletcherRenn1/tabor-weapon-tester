import json
import os
import re
from pathlib import Path


_APPDATA = os.environ.get("APPDATA", str(Path.home()))
_SUSPEND_DIR = Path(_APPDATA) / "tabor-weapon-tester" / "suspended"


def _safe_name(text: str) -> str:
    return re.sub(r"[^\w\-]", "_", text)


def get_suspend_dir() -> Path:
    _SUSPEND_DIR.mkdir(parents=True, exist_ok=True)
    return _SUSPEND_DIR


def _filepath(caliber: str, grade: int) -> Path:
    return get_suspend_dir() / f"{_safe_name(caliber)}-grade{grade}.json"


def write_suspend(data: dict) -> str:
    path = _filepath(data["caliber"], data["grade"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return str(path)


def delete_suspend(caliber: str, grade: int):
    try:
        _filepath(caliber, grade).unlink()
    except OSError:
        pass


def load_all_suspended() -> list[dict]:
    results = []
    for f in get_suspend_dir().glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            results.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return results
