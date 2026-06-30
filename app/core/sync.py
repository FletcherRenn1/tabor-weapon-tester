import hashlib
import subprocess

import requests

from app.data.config import Config


_BAD_HWIDS = {
    "00000000-0000-0000-0000-000000000000",
    "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
}


def _hwid_hash() -> str | None:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        raw = result.stdout.strip()
        if not raw or raw.upper() in _BAD_HWIDS:
            return None
        return hashlib.sha256(raw.encode()).hexdigest()
    except Exception:
        return None


class SyncClient:
    def __init__(self, config: Config, version: str):
        self._config = config
        self._version = version

    def register(self) -> bool:
        config = self._config
        endpoint = config.sync_endpoint
        if not endpoint:
            return False

        payload = {
            "user_uuid": config.user_id,
            "username": config.sync_username or None,
            "hwid_hash": _hwid_hash(),
        }
        try:
            url = endpoint.rstrip("/") + "/api/register"
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code not in (200, 201):
                return False
            config.sync_api_key = response.json()["api_key"]
            config.save()
            return True
        except Exception:
            return False

    def _ensure_registered(self) -> bool:
        if self._config.sync_api_key:
            return True
        return self.register()

    def _post(self, path: str, payload: dict) -> bool:
        endpoint = self._config.sync_endpoint
        if not endpoint or not self._ensure_registered():
            return False

        url = endpoint.rstrip("/") + path
        try:
            headers = {"Authorization": f"Bearer {self._config.sync_api_key}"}
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 401:
                self._config.sync_api_key = ""
                if not self._ensure_registered():
                    return False
                headers = {"Authorization": f"Bearer {self._config.sync_api_key}"}
                response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 403:
                return False
            return response.status_code in (200, 201)
        except Exception:
            return False

    def submit(self, results: dict) -> bool:
        if not self._config.sync_endpoint:
            return False
        payload = {
            "weapon": results.get("weapon", ""),
            "caliber": results.get("caliber", ""),
            "avg": results.get("avg", 0),
            "min_val": results.get("min_val", 0),
            "max_val": results.get("max_val", 0),
            "stddev": results.get("stddev", 0.0),
            "shots": results.get("shots", []),
            "app_version": self._version,
        }
        return self._post("/api/submit/damage", payload)

    def submit_armor(self, result: dict) -> bool:
        if not self._config.sync_endpoint:
            return False
        payload = {
            "caliber": result.get("caliber", ""),
            "grade": result.get("grade", 1),
            "base_damage": result.get("base_damage", 0),
            "base_damage_source": result.get("base_damage_source", "manual"),
            "threshold": result.get("threshold", 0),
            "total_shots": result.get("total_shots", 0),
            "pen_count": result.get("pen_count", 0),
            "blunt_count": result.get("blunt_count", 0),
            "override_count": result.get("override_count", 0),
            "pen_pct": result.get("pen_pct"),
            "ci_lower": result.get("ci_lower"),
            "ci_upper": result.get("ci_upper"),
            "margin": result.get("margin"),
            "avg_pen_damage": result.get("avg_pen_damage"),
            "avg_blunt_damage": result.get("avg_blunt_damage"),
            "pen_multiplier": result.get("pen_multiplier"),
            "blunt_multiplier": result.get("blunt_multiplier"),
            "weapon_ref": result.get("weapon_ref", ""),
            "shots": result.get("shots", []),
            "app_version": self._version,
        }
        return self._post("/api/submit/armor", payload)
