from __future__ import annotations

import time
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
        # 本地退避重试：当业务码为 99991400（频控）时，按 Retryer 的指数退避策略重试
        max_local_retries = getattr(self.http, "retryer", None).max_retries if getattr(self.http, "retryer", None) else 0
        outer_retries = 0
        total_http_retries = 0
        while True:
            status, data, http_retries = self.http.post_json("contract_search", self.url, headers, body)
            total_http_retries += http_retries

            # 成功响应优先解析业务码，其次解析数据
            if status >= 200 and status < 300 and isinstance(data, dict):
                # 顶层业务码（OpenAPI 常见风格）
                biz_code = None
                try:
                    biz_code = data.get("code")
                except Exception:
                    biz_code = None
                if biz_code == 99991663:
                    return None, total_http_retries + outer_retries, biz_code, "AUTH_FAILED"
                if biz_code == 99991400 or biz_code == 9499:
                    if outer_retries >= max_local_retries:
                        return None, total_http_retries + outer_retries, biz_code, "RETRY_EXCEEDED"
                    delay = self.http.retryer._delay(outer_retries) if getattr(self.http, "retryer", None) else 0.0
                    time.sleep(delay)
                    outer_retries += 1
                    continue

                items = ((data.get("data") or {}).get("items") or [])
                if items:
                    cid = (items[0] or {}).get("contract_id")
                    if cid:
                        return str(cid), total_http_retries + outer_retries, None, None
                return None, total_http_retries + outer_retries, None, "NOT_FOUND_CONTRACT"

            # 优先处理鉴权与限流/服务端错误（HTTP 维度）
            if status in (401, 403):
                return None, total_http_retries + outer_retries, status, "AUTH_FAILED" if status == 401 else "PERMISSION_DENIED"
            if status in (429,) or status >= 500:
                return None, total_http_retries + outer_retries, status, "RETRY_EXCEEDED"

            # 解析 4xx 的业务错误体，例如 code=110107 表示未查询到合同
            if isinstance(data, dict):
                try:
                    biz_code = data.get("code")
                except Exception:
                    biz_code = None
                biz_msg = None
                try:
                    raw_msg = data.get("msg")
                    biz_msg = str(raw_msg) if raw_msg is not None else None
                except Exception:
                    biz_msg = None

                # 业务限流码处理
                if biz_code == 99991400 or biz_code == 9499:
                    if outer_retries >= max_local_retries:
                        return None, total_http_retries + outer_retries, biz_code, "RETRY_EXCEEDED"
                    delay = self.http.retryer._delay(outer_retries) if getattr(self.http, "retryer", None) else 0.0
                    time.sleep(delay)
                    outer_retries += 1
                    continue

                if biz_code == 110107:
                    # 业务未命中：未查询到合同
                    return None, total_http_retries + outer_retries, 110107, (biz_msg or "未查询到该合同。")
                if biz_code == 99991663:
                    return None, total_http_retries + outer_retries, biz_code, "AUTH_FAILED"
                if isinstance(biz_code, int):
                    # 其他业务错误码：直接透传 code 与 msg，供上层展示
                    return None, total_http_retries + outer_retries, int(biz_code), (biz_msg or "UNKNOWN_ERROR")
            # 其他情况统一视为未知错误
            return None, total_http_retries + outer_retries, status, "UNKNOWN_ERROR"
