"""services/spam_service.py — In-memory flood & spam tracking."""

import time
from collections import defaultdict, deque
from typing import Optional

# Structure: {chat_id: {user_id: deque[timestamp]}}
_flood_tracker: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(deque))

# Track last known message text per user per chat for duplicate detection
_last_msg: dict[int, dict[int, list]] = defaultdict(lambda: defaultdict(list))


def check_flood(
    chat_id: int,
    user_id: int,
    rate: int,
    window: int,
) -> bool:
    """
    Returns True if the user is flooding (exceeded rate in window seconds).
    Registers the current message timestamp in the tracker.
    """
    now = time.monotonic()
    q = _flood_tracker[chat_id][user_id]

    # Drop timestamps outside the window
    while q and now - q[0] > window:
        q.popleft()

    q.append(now)
    return len(q) > rate


def reset_flood(chat_id: int, user_id: int) -> None:
    """Clear flood counter for a user (called after action is taken)."""
    _flood_tracker[chat_id].pop(user_id, None)


def check_duplicate(chat_id: int, user_id: int, text: str, window: int = 10) -> bool:
    """
    Returns True if the user sent the exact same text within `window` seconds.
    """
    now = time.monotonic()
    history = _last_msg[chat_id][user_id]

    # Prune old entries
    history[:] = [(t, m) for t, m in history if now - t < window]

    for _, msg in history:
        if msg == text:
            history.append((now, text))
            return True

    history.append((now, text))
    return False


def contains_link(text: str) -> bool:
    """Naive but fast link detector."""
    import re
    pattern = re.compile(
        r"(https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|tinyurl\.com/)",
        re.IGNORECASE,
    )
    return bool(pattern.search(text))


def contains_username_link(text: str) -> bool:
    """Detect @username invite patterns used for advertising."""
    import re
    return bool(re.search(r"@\w{5,}", text))
