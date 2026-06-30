import os
import re
import math
from datetime import datetime
from pathlib import Path

from app.data.config import Config

HP_PER_PERCENT = 4


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
    hp = value * HP_PER_PERCENT
    if number < 10:
        return f"Shot {number}:  {value}% ({hp} HP)"
    return f"Shot {number}: {value}% ({hp} HP)"


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
    avg_hp = round(avg * HP_PER_PERCENT, 1)
    min_hp = min_val * HP_PER_PERCENT
    max_hp = max_val * HP_PER_PERCENT
    stddev_hp = round(stddev * HP_PER_PERCENT, 1)
    lines.append(
        f"Average: {avg}% ({avg_hp} HP) | Min: {min_val}% ({min_hp} HP)"
        f" | Max: {max_val}% ({max_hp} HP) | StdDev: {stddev}% ({stddev_hp} HP)"
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
            r"Average:\s+([\d.]+)%(?:\s+\([^)]*\))?\s+\|\s+Min:\s+(\d+)%(?:\s+\([^)]*\))?"
            r"\s+\|\s+Max:\s+(\d+)%(?:\s+\([^)]*\))?\s+\|\s+StdDev:\s+([\d.]+)%",
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


def save_armor_result(result: dict) -> str:
    save_dir = _get_save_dir()
    cal_safe = _sanitize(result["caliber"])
    grade = result["grade"]
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    filepath = save_dir / f"{cal_safe}-grade{grade}-{ts}.txt"

    cal = result["caliber"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"[{cal}] vs [Grade {grade}] - {now}"]

    if result.get("weapon_ref"):
        lines.append(f"Weapon reference: {result['weapon_ref']}")

    bd = result["base_damage"]
    src = result.get("base_damage_source", "manual")
    if src == "manual":
        lines.append(f"Base damage: {bd}% (manual)")
    else:
        lines.append(f"Base damage: {bd}% (from test: {src})")

    lines.append(f"Classification threshold: {result['threshold']}%")
    lines.append("")

    tc = result["total_shots"]
    pc = result["pen_count"]
    bc = result["blunt_count"]
    oc = result["override_count"]
    lines.append(f"Total shots: {tc} | Pens: {pc} | Blunts: {bc} | Overrides: {oc}")
    lines.append("")

    pen_pct = result["pen_pct"]
    ci_lo = result["ci_lower"]
    ci_hi = result["ci_upper"]
    margin = result["margin"]
    lines.append(f"Pen chance: {pen_pct}% (90% CI: {ci_lo}% - {ci_hi}%, margin +-{margin}%)")
    lines.append("")

    avg_pen = result["avg_pen_damage"]
    avg_blunt = result["avg_blunt_damage"]
    pen_mult = result["pen_multiplier"]
    blunt_mult = result["blunt_multiplier"]

    pen_d = f"{avg_pen}%" if avg_pen is not None else "N/A"
    pen_m = f"{pen_mult}x" if pen_mult is not None else "N/A"
    blt_d = f"{avg_blunt}%" if avg_blunt is not None else "N/A"
    blt_m = f"{blunt_mult}x" if blunt_mult is not None else "N/A"
    lines.append(f"Avg pen damage:   {pen_d}  |  Pen multiplier:   {pen_m}")
    lines.append(f"Avg blunt damage: {blt_d}  |  Blunt multiplier: {blt_m}")
    lines.append("")
    lines.append("Shot log:")

    for i, shot in enumerate(result["shots"], 1):
        ov = " (override)" if shot.get("overridden") else ""
        lines.append(f"{i}   {shot['damage']}%  {shot['classification']}{ov}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return str(filepath)


def _parse_armor_file(filepath: Path) -> dict | None:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None

    lines = text.splitlines()
    if not lines:
        return None

    header_match = re.match(
        r"\[(.+?)\]\s+vs\s+\[Grade\s+(\d+)\]\s+-\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})",
        lines[0].strip(),
    )
    if not header_match:
        return None

    caliber = header_match.group(1)
    grade = int(header_match.group(2))
    try:
        date = datetime.strptime(header_match.group(3), "%Y-%m-%d %H:%M")
    except ValueError:
        return None

    r: dict = {
        "caliber": caliber, "grade": grade, "date": date,
        "weapon_ref": "", "base_damage": 0, "base_damage_source": "manual",
        "threshold": 0, "total_shots": 0, "pen_count": 0, "blunt_count": 0,
        "override_count": 0, "pen_pct": 0.0, "ci_lower": 0.0, "ci_upper": 0.0,
        "margin": 0.0, "avg_pen_damage": None, "avg_blunt_damage": None,
        "pen_multiplier": None, "blunt_multiplier": None, "shots": [],
        "filepath": str(filepath),
    }

    in_log = False
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("Weapon reference:"):
            r["weapon_ref"] = line.split(":", 1)[1].strip()
        elif line.startswith("Base damage:"):
            m = re.match(r"Base damage:\s+(\d+)%\s+\((.+?)\)", line)
            if m:
                r["base_damage"] = int(m.group(1))
                src = m.group(2)
                r["base_damage_source"] = "manual" if "manual" in src else src.replace("from test: ", "")
        elif line.startswith("Classification threshold:"):
            m = re.match(r"Classification threshold:\s+(\d+)%", line)
            if m:
                r["threshold"] = int(m.group(1))
        elif line.startswith("Total shots:"):
            m = re.match(r"Total shots:\s+(\d+)\s+\|\s+Pens:\s+(\d+)\s+\|\s+Blunts:\s+(\d+)\s+\|\s+Overrides:\s+(\d+)", line)
            if m:
                r["total_shots"] = int(m.group(1))
                r["pen_count"] = int(m.group(2))
                r["blunt_count"] = int(m.group(3))
                r["override_count"] = int(m.group(4))
        elif line.startswith("Pen chance:"):
            m = re.match(r"Pen chance:\s+([\d.]+)%\s+\(90% CI:\s+([\d.]+)%\s+-\s+([\d.]+)%,\s+margin\s+\+-([\d.]+)%\)", line)
            if m:
                r["pen_pct"] = float(m.group(1))
                r["ci_lower"] = float(m.group(2))
                r["ci_upper"] = float(m.group(3))
                r["margin"] = float(m.group(4))
        elif line.startswith("Avg pen damage:"):
            m = re.match(r"Avg pen damage:\s+([\d.]+)%.*Pen multiplier:\s+([\d.]+)x", line)
            if m:
                r["avg_pen_damage"] = float(m.group(1))
                r["pen_multiplier"] = float(m.group(2))
        elif line.startswith("Avg blunt damage:"):
            m = re.match(r"Avg blunt damage:\s+([\d.]+)%.*Blunt multiplier:\s+([\d.]+)x", line)
            if m:
                r["avg_blunt_damage"] = float(m.group(1))
                r["blunt_multiplier"] = float(m.group(2))
        elif line == "Shot log:":
            in_log = True
        elif in_log:
            m = re.match(r"(\d+)\s+(\d+)%\s+(pen|blunt)(\s+\(override\))?", line)
            if m:
                r["shots"].append({
                    "damage": int(m.group(2)),
                    "classification": m.group(3),
                    "overridden": m.group(4) is not None,
                })

    return r


def load_all_armor_results() -> list[dict]:
    save_dir = _get_save_dir()
    results = []
    for txt_file in save_dir.glob("*.txt"):
        r = _parse_armor_file(txt_file)
        if r is not None:
            results.append(r)
    results.sort(key=lambda x: x["date"], reverse=True)
    return results
