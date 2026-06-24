import os
import sys
import cv2
import pytesseract
import numpy as np
from abc import ABC, abstractmethod

from app.core.capture import ScreenCapture


def _configure_tesseract():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "..")
    exe = os.path.join(base, "assets", "tesseract", "tesseract.exe")
    if os.path.isfile(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
        os.environ["TESSDATA_PREFIX"] = os.path.join(base, "assets", "tesseract")


_configure_tesseract()


class HealthProvider(ABC):
    @abstractmethod
    def read(self) -> int | None: ...


class HealthReader(HealthProvider):
    def __init__(self, capture: ScreenCapture):
        self._capture = capture

    def read(self) -> int | None:
        try:
            img = self._capture.grab()
            processed = self._preprocess(img)
            raw = pytesseract.image_to_string(
                processed,
                config="--psm 8 -c tessedit_char_whitelist=0123456789%",
            )
            text = raw.strip().replace("%", "")
            value = int(text)
            if 0 <= value <= 100:
                return value
            return None
        except (ValueError, TypeError, Exception):
            return None

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        upscaled = cv2.resize(img, (w * 4, h * 4), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh
