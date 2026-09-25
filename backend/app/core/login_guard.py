"""Slows password guessing: too many failed logins for one account from one
address, or from one address overall, are refused for a while.

In memory, per process. That is enough for a single backend instance; run
more than one and each keeps its own count."""

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional, Tuple

WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_ACCOUNT = 5
MAX_FAILURES_PER_ADDRESS = 30

_failures: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
_lock = Lock()


def _trim(bucket: Deque[float], now: float) -> None:
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()


def seconds_until_allowed(address: str, username: str) -> Optional[int]:
    """None if a login attempt may go ahead, else how long to wait."""
    now = time.monotonic()
    with _lock:
        waits = []
        for key, limit in (((address, username.lower()), MAX_FAILURES_PER_ACCOUNT), ((address, "*"), MAX_FAILURES_PER_ADDRESS)):
            bucket = _failures[key]
            _trim(bucket, now)
            if len(bucket) >= limit:
                waits.append(int(WINDOW_SECONDS - (now - bucket[0])) + 1)
        return max(waits) if waits else None


def record_failure(address: str, username: str) -> None:
    now = time.monotonic()
    with _lock:
        _failures[(address, username.lower())].append(now)
        _failures[(address, "*")].append(now)


def record_success(address: str, username: str) -> None:
    with _lock:
        _failures.pop((address, username.lower()), None)


def reset() -> None:
    with _lock:
        _failures.clear()
