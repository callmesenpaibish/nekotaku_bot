"""utils/time_parser.py — Parse human-readable durations to seconds."""

import re
from typing import Optional

_UNITS = {
    "s": 1,
    "sec": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "w": 604800,
    "week": 604800,
    "weeks": 604800,
}

_PATTERN = re.compile(
    r"(\d+)\s*(" + "|".join(sorted(_UNITS.keys(), key=len, reverse=True)) + r")",
    re.IGNORECASE,
)


def parse_duration(text: str) -> Optional[int]:
    text = text.strip().lower()
    match = _PATTERN.fullmatch(text.replace(" ", ""))
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        return amount * _UNITS[unit]
    if text.isdigit():
        return int(text)
    return None


def seconds_to_human(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    parts = []
    for label, unit in [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
        if seconds >= unit:
            parts.append(f"{seconds // unit}{label}")
            seconds %= unit
    return " ".join(parts)
