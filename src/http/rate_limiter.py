from __future__ import annotations

import threading
import time
from typing import Dict


class _Bucket:
    def __init__(self, qpm: int) -> None:
        self.qpm = max(1, qpm)
        self.interval = 60.0 / float(self.qpm)
        self._lock = threading.Lock()
        self._next_time = 0.0

    def acquire(self) -> float:
        with self._lock:
            now = time.time()
            if now < self._next_time:
                to_sleep = self._next_time - now
                self._next_time += self.interval
                return to_sleep
            self._next_time = now + self.interval
            return 0.0

    def update_qpm(self, qpm: int) -> None:
        with self._lock:
            self.qpm = max(1, qpm)
            self.interval = 60.0 / float(self.qpm)


class RateLimiter:
    def __init__(self, qpm_map: Dict[str, int]) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[str, _Bucket] = {}
        for name, qpm in qpm_map.items():
            self._buckets[name] = _Bucket(qpm)

    def acquire(self, name: str) -> None:
        b = self._buckets.get(name)
        if not b:
            return
        to_sleep = b.acquire()
        if to_sleep > 0:
            time.sleep(to_sleep)

    def set_qpm(self, name: str, qpm: int) -> None:
        with self._lock:
            if name not in self._buckets:
                self._buckets[name] = _Bucket(qpm)
            else:
                self._buckets[name].update_qpm(qpm)
