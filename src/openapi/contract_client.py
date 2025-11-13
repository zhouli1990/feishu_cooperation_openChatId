from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..auth import AuthManager
from ..http.client import HttpClient


class ContractOpenAPIClient:
    def __init__(self, http: HttpClient, auth: AuthManager) -> None:
        self.http = http
        self.auth = auth
        self.url = "https://open.feishu.cn/open-apis/contract/v1/contracts/search"

    def search_contract_id(self, contract_number: str) -> Tuple[Optional[str], int, Optional[int], Optional[str]]:
        token = self.auth.get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "page_size": 50,
            "contract_number": contract_number,
        }
        status, data, retries = self.http.post_json("contract_search", self.url, headers, body)
        if status >= 200 and status < 300 and isinstance(data, dict):
            items = ((data.get("data") or {}).get("items") or [])
            if items:
                cid = (items[0] or {}).get("contract_id")
                if cid:
                    return str(cid), retries, None, None
            return None, retries, None, "NOT_FOUND_CONTRACT"
        if status in (401, 403):
            return None, retries, status, "AUTH_FAILED" if status == 401 else "PERMISSION_DENIED"
        if status in (429,) or status >= 500:
            return None, retries, status, "RETRY_EXCEEDED"
        return None, retries, status, "UNKNOWN_ERROR"
