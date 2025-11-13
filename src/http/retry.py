from __future__ import annotations

import random
import time
from typing import Callable, Tuple, Any


class Retryer:
    def __init__(self, max_retries: int, base_delay_ms: int, max_delay_ms: int, jitter: float) -> None:
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.jitter = jitter

    def _delay(self, attempt: int) -> float:
        delay = min(self.base_delay_ms * (2 ** attempt), self.max_delay_ms)
        j = delay * self.jitter
        delay = delay + random.uniform(-j, j)
        return max(0.0, delay) / 1000.0

    def run(self, func: Callable[[], Tuple[int, Any]], retryable: Callable[[int], bool]) -> Tuple[int, Any, int]:
        retries = 0
        while True:
            status, result = func()
            if status >= 200 and status < 300:
                return status, result, retries
            if retries >= self.max_retries or not retryable(status):
                return status, result, retries
            time.sleep(self._delay(retries))
            retries += 1
