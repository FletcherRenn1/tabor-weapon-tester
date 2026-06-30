import math


def wilson_interval(pen_count: int, total: int, z: float = 1.645) -> tuple[float, float]:
    if total == 0:
        return 0.0, 1.0
    p = pen_count / total
    z2n = z * z / total
    center = (p + z2n / 2) / (1 + z2n)
    margin = (z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))) / (1 + z2n)
    return max(0.0, center - margin), min(1.0, center + margin)


def wilson_width(pen_count: int, total: int) -> float:
    lo, hi = wilson_interval(pen_count, total)
    return hi - lo
