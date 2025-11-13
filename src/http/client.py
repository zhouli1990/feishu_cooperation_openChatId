from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import requests

from .rate_limiter import RateLimiter
from .retry import Retryer


class HttpClient:
    def __init__(self, timeout_ms: int, limiter: RateLimiter, retryer: Retryer) -> None:
        self.session = requests.Session()
        self.timeout = timeout_ms / 1000.0
        self.limiter = limiter
        self.retryer = retryer

    def _retryable(self, status: int) -> bool:
        return status in (429,) or status >= 500 or status == 0

    def _request(self, name: str, method: str, url: str, headers: Dict[str, str], body: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Tuple[int, Any, int]:
        def call() -> Tuple[int, Any]:
            self.limiter.acquire("global")
            if name:
                self.limiter.acquire(name)
            try:
                resp = self.session.request(method=method, url=url, headers=headers, json=body, params=params, timeout=self.timeout)
            except requests.RequestException:
                return 0, None
            status = resp.status_code
            if status >= 200 and status < 300:
                try:
                    return status, resp.json()
                except ValueError:
                    return status, None
            else:
                try:
                    return status, resp.json()
                except ValueError:
                    return status, resp.text
        status, data, retries = self.retryer.run(call, self._retryable)
        return status, data, retries

    def post_json(self, name: str, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Any, int]:
        return self._request(name, "POST", url, headers, body=body, params=None)

    def get(self, name: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Tuple[int, Any, int]:
        return self._request(name, "GET", url, headers, body=None, params=params)
