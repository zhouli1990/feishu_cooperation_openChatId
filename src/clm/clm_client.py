from __future__ import annotations

from typing import Optional, Tuple

from ..http.client import HttpClient


def _dig(d: dict, path: str):
    cur = d
    for k in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


class CLMClient:
    def __init__(self, http: HttpClient, session_cookie: str) -> None:
        self.http = http
        self.session_cookie = session_cookie
        self.base = "https://contract.feishu.cn"

    def _cookie_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Cookie": f"session={self.session_cookie}",
        }

    def get_cooperation_id(self, contract_id: str) -> Tuple[Optional[str], int, Optional[int], Optional[str]]:
        url = f"{self.base}/clm/api/workflow/composition/contractAndTask"
        params = {"contractId": contract_id, "withDocVersion": "true"}
        status, data, retries = self.http.get("contract_info", url, self._cookie_headers(), params)
        if status >= 200 and status < 300 and isinstance(data, dict):
            coop_id = _dig(data, "data.contract.contractInfo.cooperationId")
            if coop_id:
                return str(coop_id), retries, None, None
            return None, retries, None, "NO_COOPERATION"
        if status in (401, 403):
            return None, retries, status, "AUTH_FAILED" if status == 401 else "PERMISSION_DENIED"
        if status in (429,) or status >= 500:
            return None, retries, status, "RETRY_EXCEEDED"
        return None, retries, status, "UNKNOWN_ERROR"

    def get_open_chat_id(self, cooperation_id: str) -> Tuple[Optional[str], int, Optional[int], Optional[str]]:
        url = f"{self.base}/clm/api/cooperation/info"
        params = {"cooperationId": cooperation_id}
        status, data, retries = self.http.get("cooperation_info", url, self._cookie_headers(), params)
        if status >= 200 and status < 300 and isinstance(data, dict):
            chat_id = _dig(data, "data.openChatId")
            if chat_id:
                return str(chat_id), retries, None, None
            return None, retries, None, "NO_CHAT_GROUP"
        if status in (401, 403):
            return None, retries, status, "AUTH_FAILED" if status == 401 else "PERMISSION_DENIED"
        if status in (429,) or status >= 500:
            return None, retries, status, "RETRY_EXCEEDED"
        return None, retries, status, "UNKNOWN_ERROR"
