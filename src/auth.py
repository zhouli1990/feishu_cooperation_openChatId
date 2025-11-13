from __future__ import annotations

import time
from typing import Optional

from .http.client import HttpClient


class AuthManager:
    def __init__(self, app_id: str, app_secret: str, http: HttpClient) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.http = http
        self._token: Optional[str] = None
        self._expire_at: float = 0.0

    def get_tenant_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._expire_at - 120:
            return self._token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        body = {"app_id": self.app_id, "app_secret": self.app_secret}
        status, data, _ = self.http.post_json("auth", url, headers, body)
        if status >= 200 and status < 300 and isinstance(data, dict):
            token = data.get("tenant_access_token")
            if not token:
                raise RuntimeError("auth_failed: empty token")
            expire = data.get("expire") or data.get("expires_in") or 3600
            self._token = token
            self._expire_at = time.time() + float(expire)
            return token
        raise RuntimeError(f"auth_failed: {status}")
