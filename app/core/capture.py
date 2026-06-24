import mss
import numpy as np


class ScreenCapture:
    def __init__(self, monitor_index: int, x: int, y: int, w: int, h: int):
        self._monitor_index = monitor_index
        self._x = x
        self._y = y
        self._w = w
        self._h = h

    def grab(self) -> np.ndarray:
        with mss.mss() as sct:
            monitor = sct.monitors[self._monitor_index + 1]
            region = {
                "left": monitor["left"] + self._x,
                "top": monitor["top"] + self._y,
                "width": self._w,
                "height": self._h,
            }
            screenshot = sct.grab(region)
            img = np.array(screenshot)
            return img[:, :, :3]

    def grab_full_monitor(self) -> np.ndarray:
        with mss.mss() as sct:
            monitor = sct.monitors[self._monitor_index + 1]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            return img[:, :, :3]


def list_monitors() -> list[dict]:
    with mss.mss() as sct:
        result = []
        for i, monitor in enumerate(sct.monitors[1:]):
            result.append(
                {
                    "index": i,
                    "width": monitor["width"],
                    "height": monitor["height"],
                    "left": monitor["left"],
                    "top": monitor["top"],
                }
            )
        return result
