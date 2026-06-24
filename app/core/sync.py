import requests

from app.data.config import Config


class SyncClient:
    def __init__(self, config: Config, version: str):
        self._config = config
        self._version = version

    def submit(self, results: dict) -> bool:
        config = self._config
        endpoint = config.sync_endpoint
        if not endpoint:
            return False

        shots = results.get("shots", [])
        payload: dict = {
            "user_uuid": config.user_id,
            "username": config.sync_username,
            "weapon": results.get("weapon", ""),
            "caliber": results.get("caliber", ""),
            "avg": results.get("avg", 0),
            "min_val": results.get("min_val", 0),
            "max_val": results.get("max_val", 0),
            "stddev": results.get("stddev", 0.0),
            "app_version": self._version,
        }

        for i, val in enumerate(shots, start=1):
            payload[f"shot_{i}"] = val

        try:
            url = endpoint.rstrip("/") + "/api/submit"
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 403:
                return False
            return response.status_code in (200, 201)
        except Exception:
            return False
