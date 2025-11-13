from __future__ import annotations

import time
from typing import Dict, List

from .auth import AuthManager
from .http.client import HttpClient
from .http.rate_limiter import RateLimiter
from .http.retry import Retryer
from .io.reader import read_contract_numbers
from .io.writer import write_results
from .models import ResultRow, Status
from .openapi.contract_client import ContractOpenAPIClient
from .clm.clm_client import CLMClient


def _build_http(cfg: Dict) -> HttpClient:
    rl_cfg = cfg.get("rate_limit") or {}
    qpm = {
        "global": rl_cfg.get("global_qpm", 60),
        "contract_search": rl_cfg.get("contract_search_qpm", 60),
        "contract_info": rl_cfg.get("contract_info_qpm", 60),
        "cooperation_info": rl_cfg.get("cooperation_info_qpm", 60),
    }
    limiter = RateLimiter(qpm)
    rt_cfg = cfg.get("retry") or {}
    retryer = Retryer(rt_cfg.get("max_retries", 3), rt_cfg.get("base_delay_ms", 500), rt_cfg.get("max_delay_ms", 10000), float(rt_cfg.get("jitter", 0.2)))
    return HttpClient(rt_cfg.get("timeout_ms", 8000), limiter, retryer)


def run(cfg: Dict) -> None:
    files = cfg.get("files") or {}
    input_txt = files.get("input_txt")
    output_excel = files.get("output_excel")

    http = _build_http(cfg)
    auth_cfg = cfg.get("auth") or {}
    auth = AuthManager(auth_cfg.get("app_id") or "", auth_cfg.get("app_secret") or "", http)
    clm = CLMClient(http, (auth_cfg.get("cookies") or {}).get("session") or "")
    openapi = ContractOpenAPIClient(http, auth)

    nums = read_contract_numbers(input_txt)
    total = len(nums)
    results: List[ResultRow] = []

    start = time.time()
    succ = fail = 0

    for i, code in enumerate(nums):
        c_id = coop_id = chat_id = None
        status = Status.UNKNOWN_ERROR
        err_code = None
        err_msg = None

        c_id, r1, scode, smsg = openapi.search_contract_id(code)
        if c_id is None:
            if smsg == "NOT_FOUND_CONTRACT":
                status = Status.NOT_FOUND_CONTRACT
            elif smsg == "AUTH_FAILED":
                status = Status.AUTH_FAILED
            elif smsg == "PERMISSION_DENIED":
                status = Status.PERMISSION_DENIED
            elif smsg == "RETRY_EXCEEDED":
                status = Status.RETRY_EXCEEDED
            else:
                status = Status.UNKNOWN_ERROR
            err_code = str(scode) if scode else None
            err_msg = smsg
        else:
            coop_id, r2, icode, imsg = clm.get_cooperation_id(c_id)
            if coop_id is None:
                if imsg == "NO_COOPERATION":
                    status = Status.NO_COOPERATION
                elif imsg == "AUTH_FAILED":
                    status = Status.AUTH_FAILED
                elif imsg == "PERMISSION_DENIED":
                    status = Status.PERMISSION_DENIED
                elif imsg == "RETRY_EXCEEDED":
                    status = Status.RETRY_EXCEEDED
                else:
                    status = Status.UNKNOWN_ERROR
                err_code = str(icode) if icode else None
                err_msg = imsg
            else:
                chat_id, r3, ocode, omsg = clm.get_open_chat_id(coop_id)
                if chat_id is None:
                    if omsg == "NO_CHAT_GROUP":
                        status = Status.NO_CHAT_GROUP
                    elif omsg == "AUTH_FAILED":
                        status = Status.AUTH_FAILED
                    elif omsg == "PERMISSION_DENIED":
                        status = Status.PERMISSION_DENIED
                    elif omsg == "RETRY_EXCEEDED":
                        status = Status.RETRY_EXCEEDED
                    else:
                        status = Status.UNKNOWN_ERROR
                    err_code = str(ocode) if ocode else None
                    err_msg = omsg
                else:
                    status = Status.SUCCESS
                    err_code = None
                    err_msg = None

        if status == Status.SUCCESS:
            succ += 1
        else:
            fail += 1

        results.append(ResultRow(
            contract_number=code,
            contract_id=c_id,
            cooperation_id=coop_id,
            openChatId=chat_id,
            status=status,
            error_code=err_code,
            error_message=err_msg,
        ))

        elapsed = time.time() - start
        done = i + 1
        avg = elapsed / max(1, done)
        remain = total - done
        eta = avg * remain
        print(f"进度 {done}/{total} | 成功 {succ} 失败 {fail} | 预计剩余 {int(eta)}s")

    write_results(output_excel, results)
    print(f"完成。总计 {total}，成功 {succ}，失败 {fail}。输出：{output_excel}")
