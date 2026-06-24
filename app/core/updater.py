import os
import sys
import tempfile
import requests

from app.data.config import Config


GITHUB_API = "https://api.github.com/repos/FletcherRenn1/tabor-weapon-tester/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    tag = tag.lstrip("v")
    parts = tag.split(".")
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    return tuple(result)


class Updater:
    def __init__(self, current_version: str, config: Config):
        self._current_version = current_version
        self._config = config

    def check(self) -> dict | None:
        try:
            response = requests.get(GITHUB_API, timeout=10)
            response.raise_for_status()
            data = response.json()
            tag = data.get("tag_name", "")
            if not tag:
                return None

            remote_ver = _parse_version(tag)
            current_ver = _parse_version(self._current_version)

            if remote_ver <= current_ver:
                return None

            assets = data.get("assets", [])
            download_url = None
            for asset in assets:
                name = asset.get("name", "")
                if name.endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break

            if not download_url:
                return None

            return {
                "version": tag,
                "download_url": download_url,
            }
        except Exception:
            return None

    def download_and_install(self, download_url: str, current_exe_path: str):
        try:
            response = requests.get(download_url, timeout=120, stream=True)
            response.raise_for_status()

            temp_dir = tempfile.mkdtemp()
            exe_name = os.path.basename(current_exe_path)
            temp_exe = os.path.join(temp_dir, exe_name)

            with open(temp_exe, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            batch_path = os.path.join(temp_dir, "update.bat")
            batch_content = (
                "@echo off\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f'move /y "{temp_exe}" "{current_exe_path}"\r\n'
                f'start "" "{current_exe_path}"\r\n'
            )

            with open(batch_path, "w", encoding="utf-8") as f:
                f.write(batch_content)

            os.startfile(batch_path)
            sys.exit(0)
        except Exception:
            pass
