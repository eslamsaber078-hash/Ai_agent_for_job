"""In-process memo for the expensive read paths, dropped whenever a write lands.

Every read in this app is per-owner, and a write (an import, a profile edit, a tracker
change) is rare next to the reads it invalidates. A generation stamp per owner lets a
whole family of keys die at once, and a value that was computed while a write was
landing is never stored — otherwise the slow request that raced the write would pin
its own stale answer for the whole TTL.
"""
import threading
import time
from collections import OrderedDict

# Enough room for the daily users of one small instance; a bigger audience evicts the
# coldest owner instead of growing without limit.
MAX_ENTRIES = 32

_lock = threading.Lock()
_generation = 0
_owner_generation: dict[int, int] = {}
_entries: "OrderedDict[tuple, tuple[float, int, object]]" = OrderedDict()
_compute_locks: dict[tuple, threading.Lock] = {}


def invalidate(profile_id: int | None = None) -> None:
    """Forget cached reads for one owner, or for everyone."""
    global _generation
    with _lock:
        _generation += 1
        if profile_id is None:
            _entries.clear()
            _owner_generation.clear()
            _compute_locks.clear()
            return
        _owner_generation[profile_id] = _generation
        for key in [k for k in _entries if k[0] == profile_id]:
            del _entries[key]
        # Idle gates are worth nothing once the owner's values are gone; a busy one is
        # left alone so the thread already waiting on it is not split in two.
        for key in [k for k, gate in _compute_locks.items()
                    if k[0] == profile_id and not gate.locked()]:
            del _compute_locks[key]


def _stamp(profile_id: int) -> int:
    return _owner_generation.get(profile_id, 0)


def _fresh(key: tuple, profile_id: int):
    hit = _entries.get(key)
    if hit is not None and hit[0] > time.monotonic():
        _entries.move_to_end(key)
        return hit[2]
    return None


def cached(profile_id: int, kind: str, ttl: float, produce):
    """Return the memoized value of ``produce()`` for this owner and kind.

    A cold key is computed by one thread only: a page opened by a hundred sessions
    at once must not start a hundred copies of the same ranking.
    """
    key = (profile_id, kind)
    with _lock:
        value = _fresh(key, profile_id)
        if value is not None:
            return value
        gate = _compute_locks.get(key)
        if gate is None:
            gate = _compute_locks[key] = threading.Lock()
    with gate:
        with _lock:
            value = _fresh(key, profile_id)
            if value is not None:
                return value
            stamp = _stamp(profile_id)
        value = produce()
        with _lock:
            if stamp == _stamp(profile_id):
                _entries[key] = (time.monotonic() + ttl, stamp, value)
                _entries.move_to_end(key)
                while len(_entries) > MAX_ENTRIES:
                    _entries.popitem(last=False)
        return value


def clear() -> None:
    invalidate(None)
