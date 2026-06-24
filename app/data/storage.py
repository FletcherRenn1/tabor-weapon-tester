import os
import re
import math
from datetime import datetime
from pathlib import Path

from app.data.config import Config


def _sanitize(text: str) -> str:
    text = text.replace(" ", "_")
    text = re.sub(r"[^\w\-]", "", text)
    return text


def _get_save_dir() -> Path:
    config = Config.get()
    path = Path(config.save_location)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_filename(weapon: str, caliber: str, mode: str) -> str:
    w = _sanitize(weapon)
    c = _sanitize(caliber)
    if mode == "new_file":
        ts = datetime.now().strftime("%Y-%m-%d-%H%M")
        return f"{w}-{c}-{ts}.txt"
    return f"{w}-{c}.txt"


def _format_shot_line(number: int, value: int) -> str:
    if number < 10:
        return f"Shot {number}:  {value}%"
    return f"Shot {number}: {value}%"


def _compute_stddev(shots: list[int], avg: float) -> float:
    if len(shots) < 2:
        return 0.0
    variance = sum((s - avg) ** 2 for s in shots) / len(shots)
    return round(math.sqrt(variance), 1)


def save_result(
    weapon: str,
    caliber: str,
    shots: list[int],
    avg: float,
    min_val: int,
    max_val: int,
    stddev: float,
) -> str:
    config = Config.get()
    save_dir = _get_save_dir()
    filename = _build_filename(weapon, caliber, "new_file")
    filepath = save_dir / filename

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"[{weapon}] [{caliber}] - {now}")
    for i, val in enumerate(shots, start=1):
        lines.append(_format_shot_line(i, val))
    lines.append("")
    lines.append(
        f"Average: {avg}% | Min: {min_val}% | Max: {max_val}% | StdDev: {stddev}%"
    )
    lines.append("")

    with open(filepath, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return str(filepath)


def _parse_block(lines: list[str]) -> dict | None:
    if not lines:
        return None

    header = lines[0].strip()
    header_match = re.match(
        r"\[(.+?)\]\s+\[(.+?)\]\s+-\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", header
    )
    if not header_match:
        return None

    weapon = header_match.group(1)
    caliber = header_match.group(2)
    date_str = header_match.group(3)

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return None

    shots = []
    avg = None
    min_val = None
    max_val = None
    stddev = None

    for line in lines[1:]:
        line = line.strip()
        shot_match = re.match(r"Shot\s+(\d+):\s+(\d+)%", line)
        if shot_match:
            shots.append(int(shot_match.group(2)))
            continue
        summary_match = re.match(
            r"Average:\s+([\d.]+)%\s+\|\s+Min:\s+(\d+)%\s+\|\s+Max:\s+(\d+)%\s+\|\s+StdDev:\s+([\d.]+)%",
            line,
        )
        if summary_match:
            avg = float(summary_match.group(1))
            min_val = int(summary_match.group(2))
            max_val = int(summary_match.group(3))
            stddev = float(summary_match.group(4))

    if not shots:
        return None

    if avg is None:
        avg = round(sum(shots) / len(shots), 1)
    if min_val is None:
        min_val = min(shots)
    if max_val is None:
        max_val = max(shots)
    if stddev is None:
        stddev = _compute_stddev(shots, avg)

    return {
        "weapon": weapon,
        "caliber": caliber,
        "date": date,
        "shots": shots,
        "avg": avg,
        "min_val": min_val,
        "max_val": max_val,
        "stddev": stddev,
    }


def _parse_file(filepath: Path) -> list[dict]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []

    raw_lines = content.splitlines()
    blocks = []
    current_block: list[str] = []

    for line in raw_lines:
        if re.match(r"\[.+?\]\s+\[.+?\]\s+-\s+\d{4}-\d{2}-\d{2}", line):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        blocks.append(current_block)

    results = []
    for block in blocks:
        parsed = _parse_block(block)
        if parsed is not None:
            parsed["filepath"] = str(filepath)
            results.append(parsed)

    return results


def load_all_results() -> list[dict]:
    save_dir = _get_save_dir()
    all_results = []

    for txt_file in save_dir.glob("*.txt"):
        file_results = _parse_file(txt_file)
        all_results.extend(file_results)

    all_results.sort(key=lambda r: r["date"], reverse=True)
    return all_results


def delete_all_results():
    save_dir = _get_save_dir()
    for txt_file in save_dir.glob("*.txt"):
        try:
            txt_file.unlink()
        except OSError:
            pass
