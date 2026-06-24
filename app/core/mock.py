import random

from app.core.ocr import HealthProvider


class MockHealthProvider(HealthProvider):
    def __init__(self):
        self._health = 100
        self._noise = False

    @property
    def current_health(self) -> int:
        return self._health

    @current_health.setter
    def current_health(self, value: int):
        self._health = max(0, min(100, value))

    @property
    def noise_enabled(self) -> bool:
        return self._noise

    @noise_enabled.setter
    def noise_enabled(self, value: bool):
        self._noise = value

    def inject_value(self, n: int):
        self._health = max(0, min(100, n))

    def apply_damage(self, amount: int):
        self._health = max(0, self._health - amount)

    def read(self) -> int | None:
        if self._noise:
            return max(0, min(100, self._health + random.randint(-2, 2)))
        return self._health
