import json
import os
import uuid
from pathlib import Path


_APPDATA = os.environ.get("APPDATA", str(Path.home()))
_CONFIG_DIR = Path(_APPDATA) / "tabor-weapon-tester"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_DEFAULT_SAVE_LOCATION = str(_CONFIG_DIR / "results") + os.sep


def _default_config() -> dict:
    return {
        "user_id": str(uuid.uuid4()),
        "wizard_complete": False,
        "save_location": _DEFAULT_SAVE_LOCATION,
        "file_naming_mode": "append",
        "safety_buffer": 20,
        "default_weapon": "",
        "default_caliber": "",
        "active_profile": "",
        "calibration_profiles": {},
        "tts_enabled": True,
        "tts_volume": 0.8,
        "tts_voice": "",
        "tts_events": {
            "ready": True,
            "shoot": True,
            "recorded": True,
            "heal": True,
            "complete": True,
            "update": True,
        },
        "updates_enabled": False,
        "updates_opted_in": False,
        "permanent_optout_updates": False,
        "sync_enabled": False,
        "sync_opted_in": False,
        "permanent_optout_sync": False,
        "sync_username": "",
        "sync_endpoint": "",
        "mock_mode": False,
    }


def _apply_defaults(data: dict, defaults: dict) -> dict:
    result = dict(data)
    for key, value in defaults.items():
        if key not in result:
            result[key] = value
        elif isinstance(value, dict) and isinstance(result[key], dict):
            result[key] = _apply_defaults(result[key], value)
    return result


class Config:
    _instance: "Config | None" = None

    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls) -> "Config":
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        defaults = _default_config()

        if _CONFIG_FILE.exists():
            try:
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                data = _apply_defaults(raw, defaults)
            except (json.JSONDecodeError, OSError):
                data = defaults
        else:
            data = defaults

        instance = cls(data)
        cls._instance = instance
        instance.save()
        return instance

    @classmethod
    def get(cls) -> "Config":
        if cls._instance is None:
            return cls.load()
        return cls._instance

    def save(self):
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def __getattr__(self, name: str):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"Config has no attribute {name!r}")

    def __setattr__(self, name: str, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def get_value(self, key: str, default=None):
        return self._data.get(key, default)

    def set_value(self, key: str, value):
        self._data[key] = value

    def to_dict(self) -> dict:
        return dict(self._data)
