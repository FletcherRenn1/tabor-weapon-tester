import time
from datetime import datetime
from enum import Enum

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.core.ocr import HealthProvider
from app.core.statistics import wilson_interval, wilson_width
from app.core.suspend import write_suspend, delete_suspend
from app.data.config import Config


_MIN_SHOTS = 30
_TARGET_WIDTH = 0.10
_EARLY_STOP_SHOTS = 50


class ArmorState(Enum):
    IDLE = "IDLE"
    WAITING_FOR_FULL_HEALTH = "WAITING_FOR_FULL_HEALTH"
    READY_TO_SHOOT = "READY_TO_SHOOT"
    WAITING_FOR_HIT = "WAITING_FOR_HIT"
    RECORDING_VALUE = "RECORDING_VALUE"
    HEAL_WARNING = "HEAL_WARNING"
    REVIEW = "REVIEW"
    PAUSED = "PAUSED"
    SUSPENDED = "SUSPENDED"


class ArmorSession(QObject):
    state_changed = pyqtSignal(str)
    shot_recorded = pyqtSignal(int, str, int)
    health_updated = pyqtSignal(int)
    stats_updated = pyqtSignal(dict)
    override_rate_warning = pyqtSignal()
    entered_review = pyqtSignal()

    def __init__(self, provider: HealthProvider, config: Config, version: str = "0.0.0"):
        super().__init__()
        self._provider = provider
        self._config = config
        self._version = version

        self._caliber = ""
        self._grade = 1
        self._base_damage = 0
        self._threshold = 0
        self._weapon_ref = ""
        self._base_damage_source = "manual"

        self._shots: list[dict] = []

        self._health_before = 100
        self._current_health = 100
        self._stab_value: int | None = None
        self._stab_start = 0.0
        self._drop_start = 0.0
        self._pre_pause_state = ArmorState.IDLE
        self._state = ArmorState.IDLE

        self._timer = QTimer()
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll)

    @property
    def current_state(self) -> ArmorState:
        return self._state

    @property
    def caliber(self) -> str:
        return self._caliber

    @property
    def grade(self) -> int:
        return self._grade

    @property
    def base_damage(self) -> int:
        return self._base_damage

    @property
    def threshold(self) -> int:
        return self._threshold

    @property
    def weapon_ref(self) -> str:
        return self._weapon_ref

    @property
    def base_damage_source(self) -> str:
        return self._base_damage_source

    @property
    def shots(self) -> list[dict]:
        return list(self._shots)

    def start(
        self,
        caliber: str,
        grade: int,
        base_damage: int,
        threshold: int,
        weapon_ref: str = "",
        base_damage_source: str = "manual",
    ):
        if self._state != ArmorState.IDLE:
            return
        self._caliber = caliber
        self._grade = grade
        self._base_damage = base_damage
        self._threshold = threshold
        self._weapon_ref = weapon_ref
        self._base_damage_source = base_damage_source
        self._shots = []
        self._stab_value = None
        self._stab_start = 0.0
        self._drop_start = 0.0
        self._set_state(ArmorState.WAITING_FOR_FULL_HEALTH)
        self._timer.start()

    def load_suspended(self, data: dict):
        if self._state != ArmorState.IDLE:
            return
        self._caliber = data["caliber"]
        self._grade = data["grade"]
        self._base_damage = data["base_damage"]
        self._threshold = data["threshold"]
        self._weapon_ref = data.get("weapon_reference", "")
        self._base_damage_source = data.get("base_damage_source", "manual")
        self._shots = list(data.get("shots", []))
        self._stab_value = None
        self._stab_start = 0.0
        self._drop_start = 0.0
        self._set_state(ArmorState.WAITING_FOR_FULL_HEALTH)
        self._timer.start()
        self._emit_stats()

    def pause(self):
        if self._state in (ArmorState.IDLE, ArmorState.PAUSED, ArmorState.REVIEW, ArmorState.SUSPENDED):
            return
        self._pre_pause_state = self._state
        self._set_state(ArmorState.PAUSED)

    def resume(self):
        if self._state != ArmorState.PAUSED:
            return
        self._set_state(ArmorState.WAITING_FOR_FULL_HEALTH)

    def suspend(self):
        self._timer.stop()
        self._write_suspend()
        self._set_state(ArmorState.SUSPENDED)

    def cancel(self):
        self._timer.stop()
        self._shots = []
        self._set_state(ArmorState.IDLE)

    def override_shot(self, index: int, new_classification: str):
        if index < 0 or index >= len(self._shots):
            return
        if self._shots[index]["classification"] == new_classification:
            return
        self._shots[index]["classification"] = new_classification
        self._shots[index]["overridden"] = True
        self._emit_stats()
        total = len(self._shots)
        overrides = sum(1 for s in self._shots if s["overridden"])
        if overrides / total > 0.30:
            self.override_rate_warning.emit()

    def get_result(self) -> dict:
        stats = self.get_stats()
        return {
            "caliber": self._caliber,
            "grade": self._grade,
            "total_shots": stats["total"],
            "pen_count": stats["pen_count"],
            "blunt_count": stats["blunt_count"],
            "override_count": stats["override_count"],
            "pen_pct": stats["pen_pct"],
            "ci_lower": stats["ci_lower"],
            "ci_upper": stats["ci_upper"],
            "margin": stats["margin"],
            "avg_pen_damage": stats["avg_pen_damage"],
            "avg_blunt_damage": stats["avg_blunt_damage"],
            "pen_multiplier": stats["pen_multiplier"],
            "blunt_multiplier": stats["blunt_multiplier"],
            "base_damage": self._base_damage,
            "base_damage_source": self._base_damage_source,
            "threshold": self._threshold,
            "weapon_ref": self._weapon_ref,
            "shots": list(self._shots),
            "date": datetime.now(),
        }

    def finalise(self):
        self._timer.stop()
        delete_suspend(self._caliber, self._grade)
        self._set_state(ArmorState.IDLE)

    def _set_state(self, s: ArmorState):
        self._state = s
        self.state_changed.emit(s.value)

    def _enter_ready(self, health: int):
        self._health_before = health
        self._drop_start = 0.0
        self._stab_value = None
        self._set_state(ArmorState.READY_TO_SHOOT)

    def _poll(self):
        raw = self._provider.read()
        if raw is None:
            return
        self.health_updated.emit(raw)
        self._current_health = raw
        s = self._state

        if s == ArmorState.WAITING_FOR_FULL_HEALTH:
            if raw >= 98:
                self._enter_ready(raw)

        elif s == ArmorState.READY_TO_SHOOT:
            if raw < self._health_before:
                now = time.monotonic()
                if self._drop_start == 0.0:
                    self._drop_start = now
                elif (now - self._drop_start) >= 0.8:
                    self._drop_start = 0.0
                    self._stab_value = None
                    self._stab_start = 0.0
                    self._set_state(ArmorState.WAITING_FOR_HIT)
            else:
                self._drop_start = 0.0

        elif s == ArmorState.WAITING_FOR_HIT:
            now = time.monotonic()
            if self._stab_value is None or self._stab_value != raw:
                self._stab_value = raw
                self._stab_start = now
            elif (now - self._stab_start) >= 0.8:
                self._set_state(ArmorState.RECORDING_VALUE)
                self._record_shot(raw)

        elif s == ArmorState.HEAL_WARNING:
            if raw >= 98:
                self._enter_ready(raw)

    def _record_shot(self, health_after: int):
        damage = max(0, self._health_before - health_after)
        classification = "pen" if damage > self._threshold else "blunt"
        self._shots.append({"damage": damage, "classification": classification, "overridden": False})
        n = len(self._shots)
        pen_count = sum(1 for s in self._shots if s["classification"] == "pen")
        width = wilson_width(pen_count, n)

        self.shot_recorded.emit(n, classification, damage)
        self._emit_stats()

        if n % 10 == 0:
            self._write_suspend()

        if self._is_complete(pen_count, n, width):
            self._timer.stop()
            self._set_state(ArmorState.REVIEW)
            self.entered_review.emit()
            return

        stats = self.get_stats()
        candidates = [d for d in [stats["avg_pen_damage"], stats["avg_blunt_damage"]] if d is not None]
        if candidates and (health_after - min(candidates)) <= self._config.safety_buffer:
            self._set_state(ArmorState.HEAL_WARNING)
        else:
            self._enter_ready(health_after)

    def _is_complete(self, pen_count: int, total: int, width: float) -> bool:
        if total < _MIN_SHOTS:
            return False
        if total >= _EARLY_STOP_SHOTS and pen_count == 0:
            return True
        if total >= _EARLY_STOP_SHOTS and pen_count == total:
            return True
        return width <= _TARGET_WIDTH

    def _emit_stats(self):
        self.stats_updated.emit(self.get_stats())

    def get_stats(self) -> dict:
        total = len(self._shots)
        if total == 0:
            return {
                "total": 0, "pen_count": 0, "blunt_count": 0, "override_count": 0,
                "pen_pct": 0.0, "ci_lower": 0.0, "ci_upper": 100.0, "margin": 50.0,
                "ci_width": 1.0, "avg_pen_damage": None, "avg_blunt_damage": None,
                "pen_multiplier": None, "blunt_multiplier": None,
                "shots_estimate": "estimating...",
            }

        pen_shots = [s for s in self._shots if s["classification"] == "pen"]
        blunt_shots = [s for s in self._shots if s["classification"] == "blunt"]
        pen_count = len(pen_shots)
        blunt_count = len(blunt_shots)
        override_count = sum(1 for s in self._shots if s["overridden"])

        lo, hi = wilson_interval(pen_count, total)
        width = hi - lo

        avg_pen = round(sum(s["damage"] for s in pen_shots) / pen_count, 1) if pen_count else None
        avg_blunt = round(sum(s["damage"] for s in blunt_shots) / blunt_count, 1) if blunt_count else None
        bd = self._base_damage
        pen_mult = round(avg_pen / bd, 3) if avg_pen is not None and bd > 0 else None
        blunt_mult = round(avg_blunt / bd, 3) if avg_blunt is not None and bd > 0 else None

        return {
            "total": total,
            "pen_count": pen_count,
            "blunt_count": blunt_count,
            "override_count": override_count,
            "pen_pct": round(pen_count / total * 100, 1),
            "ci_lower": round(lo * 100, 1),
            "ci_upper": round(hi * 100, 1),
            "margin": round((hi - lo) / 2 * 100, 1),
            "ci_width": width,
            "avg_pen_damage": avg_pen,
            "avg_blunt_damage": avg_blunt,
            "pen_multiplier": pen_mult,
            "blunt_multiplier": blunt_mult,
            "shots_estimate": self._estimate(total, pen_count, lo, hi, width),
        }

    def _shots_needed_for(self, p: float) -> int:
        n = 1
        cap = 200_000
        while wilson_width(round(p * n), n) > _TARGET_WIDTH and n < cap:
            n *= 2
        lo_n, hi_n = n // 2 or 1, min(n, cap)
        while lo_n < hi_n:
            mid = (lo_n + hi_n) // 2
            if wilson_width(round(p * mid), mid) > _TARGET_WIDTH:
                lo_n = mid + 1
            else:
                hi_n = mid
        return lo_n

    def _estimate(self, total: int, pen_count: int, ci_lo: float, ci_hi: float, width: float) -> str:
        if width <= _TARGET_WIDTH:
            return "almost done"
        if total < 5:
            return "estimating..."

        p_hat = pen_count / total
        candidates = [p_hat, ci_lo, ci_hi]
        if ci_lo <= 0.5 <= ci_hi:
            candidates.append(0.5)

        needed_totals = [self._shots_needed_for(p) for p in candidates]
        lo_more = max(1, min(needed_totals) - total)
        hi_more = max(lo_more, max(needed_totals) - total)
        return f"~{lo_more}-{hi_more} more shots"

    def _write_suspend(self):
        write_suspend({
            "caliber": self._caliber,
            "grade": self._grade,
            "base_damage": self._base_damage,
            "threshold": self._threshold,
            "shots": list(self._shots),
            "total_shots": len(self._shots),
            "pen_count": sum(1 for s in self._shots if s["classification"] == "pen"),
            "suspended_at": datetime.now().isoformat(timespec="seconds"),
            "weapon_reference": self._weapon_ref,
            "base_damage_source": self._base_damage_source,
            "app_version": self._version,
        })
