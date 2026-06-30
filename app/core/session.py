import math
import time
from enum import Enum

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.core.ocr import HealthProvider
from app.data.config import Config


class State(Enum):
    IDLE = "IDLE"
    SETUP = "SETUP"
    WAITING_FOR_FULL_HEALTH = "WAITING_FOR_FULL_HEALTH"
    READY_TO_SHOOT = "READY_TO_SHOOT"
    WAITING_FOR_HIT = "WAITING_FOR_HIT"
    RECORDING_VALUE = "RECORDING_VALUE"
    HEAL_WARNING = "HEAL_WARNING"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"


def _stddev(shots: list[int]) -> float:
    if len(shots) < 2:
        return 0.0
    avg = sum(shots) / len(shots)
    variance = sum((s - avg) ** 2 for s in shots) / len(shots)
    return round(math.sqrt(variance), 1)


class Session(QObject):
    state_changed = pyqtSignal(str)
    shot_recorded = pyqtSignal(int, int)
    health_updated = pyqtSignal(int)
    test_complete = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, provider: HealthProvider, config: Config):
        super().__init__()
        self._provider = provider
        self._config = config
        self._state = State.IDLE
        self._weapon = ""
        self._caliber = ""
        self._shots: list[int] = []
        self._health_before_shot: int = 100
        self._current_health: int = 100
        self._stabilize_value: int | None = None
        self._stabilize_start: float = 0.0
        self._drop_detected_start: float = 0.0
        self._pre_pause_state: State = State.IDLE
        self._timer = QTimer()
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll)

    def _set_state(self, state: State):
        self._state = state
        self.state_changed.emit(state.value)

    @property
    def current_state(self) -> State:
        return self._state

    def start(self, weapon: str, caliber: str):
        if self._state != State.IDLE:
            return
        self._weapon = weapon
        self._caliber = caliber
        self._shots = []
        self._stabilize_value = None
        self._drop_detected_start = 0.0
        self._set_state(State.SETUP)
        self._set_state(State.WAITING_FOR_FULL_HEALTH)
        self._timer.start()

    def pause(self):
        if self._state in (State.IDLE, State.PAUSED, State.COMPLETE):
            return
        self._pre_pause_state = self._state
        self._set_state(State.PAUSED)

    def resume(self):
        if self._state != State.PAUSED:
            return
        self._set_state(State.WAITING_FOR_FULL_HEALTH)

    def cancel(self):
        self._timer.stop()
        self._shots = []
        self._set_state(State.IDLE)

    def _enter_ready(self, health: int):
        self._health_before_shot = health
        self._drop_detected_start = 0.0
        self._stabilize_value = None
        self._set_state(State.READY_TO_SHOOT)

    def _poll(self):
        raw = self._provider.read()
        if raw is None:
            return

        value = raw
        self.health_updated.emit(value)
        self._current_health = value

        state = self._state

        if state == State.WAITING_FOR_FULL_HEALTH:
            # >=98 so a single bad OCR frame near full health doesn't block
            if value >= 98:
                self._enter_ready(value)

        elif state == State.READY_TO_SHOOT:
            threshold = self._health_before_shot
            if value < threshold:
                now = time.monotonic()
                if self._drop_detected_start == 0.0:
                    self._drop_detected_start = now
                elif (now - self._drop_detected_start) >= 0.5:
                    self._drop_detected_start = 0.0
                    self._stabilize_value = None
                    self._stabilize_start = 0.0
                    self._set_state(State.WAITING_FOR_HIT)
            else:
                self._drop_detected_start = 0.0

        elif state == State.WAITING_FOR_HIT:
            now = time.monotonic()
            if self._stabilize_value is None or self._stabilize_value != value:
                self._stabilize_value = value
                self._stabilize_start = now
            elif (now - self._stabilize_start) >= 0.8:
                self._set_state(State.RECORDING_VALUE)
                self._record_shot(value)

        elif state == State.HEAL_WARNING:
            if value >= 98:
                self._enter_ready(value)

        elif state == State.PAUSED:
            pass

    def _record_shot(self, health_after: int):
        damage = self._health_before_shot - health_after
        if damage < 0:
            damage = 0
        self._shots.append(damage)
        shot_number = len(self._shots)
        self.shot_recorded.emit(shot_number, damage)

        if shot_number == 10:
            self._timer.stop()
            self._set_state(State.COMPLETE)
            self.test_complete.emit(self._build_results())
            return

        avg_damage = sum(self._shots) / len(self._shots)
        if (health_after - avg_damage) <= self._config.safety_buffer:
            self._stabilize_value = None
            self._set_state(State.HEAL_WARNING)
        else:
            self._enter_ready(health_after)

    def _build_results(self) -> dict:
        shots = self._shots
        avg = round(sum(shots) / len(shots), 1)
        return {
            "weapon": self._weapon,
            "caliber": self._caliber,
            "shots": shots,
            "avg": avg,
            "min_val": min(shots),
            "max_val": max(shots),
            "stddev": _stddev(shots),
            "safety_buffer": self._config.safety_buffer,
        }
