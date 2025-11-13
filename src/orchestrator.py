from __future__ import annotations

import time
from typing import Dict, List

from pathlib import Path
from .auth import AuthManager
from .http.client import HttpClient
from .http.rate_limiter import RateLimiter
from .http.retry import Retryer
from .io.reader import read_contract_numbers, read_results_excel
from .io.writer import write_results
from .models import ResultRow, Status
from .openapi.contract_client import ContractOpenAPIClient
from .clm.clm_client import CLMClient
from .logger import JsonLogger


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
    log_file = files.get("log_file") or "./logs/run.log"

    http = _build_http(cfg)
    auth_cfg = cfg.get("auth") or {}
    auth = AuthManager(auth_cfg.get("app_id") or "", auth_cfg.get("app_secret") or "", http)
    clm = CLMClient(http, (auth_cfg.get("cookies") or {}).get("session") or "")
    openapi = ContractOpenAPIClient(http, auth)

    log_cfg = cfg.get("log") or {}
    log_level = (log_cfg.get("level") or "INFO")
    logger = JsonLogger(log_file, module="orchestrator", level=log_level)
    trace_id = JsonLogger.new_trace_id()
    logger = logger.with_context({"traceId": trace_id})

    nums = read_contract_numbers(input_txt)

    existing_order: List[str] = []
    existing_map: Dict[str, ResultRow] = {}
    if Path(output_excel).exists():
        existing_order, existing_map = read_results_excel(output_excel)

    retry_cfg = cfg.get("retry") or {}
    skip_status_names = retry_cfg.get("skip_result_statuses") or []
    skip_statuses = {Status(name) for name in skip_status_names}

    todo_nums: List[str] = []
    for code in nums:
        r = existing_map.get(code)
        if r and r.status in skip_statuses:
            logger.info("skip_existing", {
                "contract_number": code,
                "status": r.status.value,
                "reason": "skip_result_statuses",
            })
            continue
        todo_nums.append(code)

    total = len(todo_nums)
    results: List[ResultRow] = []

    start = time.time()
    succ = fail = 0

    logger.info("batch_start", {
        "total": total,
        "concurrency": (cfg.get("rate_limit") or {}).get("concurrency", 1),
    })

    for i, code in enumerate(todo_nums):
        c_id = coop_id = chat_id = None
        status = Status.UNKNOWN_ERROR
        err_code = None
        err_msg = None

        step_start = time.perf_counter()
        logger.info("SEARCH start", {"step": "SEARCH", "contract_number": code})
        c_id, r1, scode, smsg = openapi.search_contract_id(code)
        elapsed = int((time.perf_counter() - step_start) * 1000)
        if c_id is None:
            # 先按业务码判断：110107 表示未查询到合同
            if scode == 110107:
                status = Status.NOT_FOUND_CONTRACT
            elif smsg == "NOT_FOUND_CONTRACT":
                status = Status.NOT_FOUND_CONTRACT
            elif smsg == "AUTH_FAILED":
                status = Status.AUTH_FAILED
            elif smsg == "PERMISSION_DENIED":
                status = Status.PERMISSION_DENIED
            elif smsg == "RETRY_EXCEEDED":
                status = Status.RETRY_EXCEEDED
            else:
                status = Status.UNKNOWN_ERROR
            err_code = str(scode) if scode is not None else None
            err_msg = smsg
            logger.warn("SEARCH failed", {
                "step": "SEARCH",
                "contract_number": code,
                "httpStatus": scode,
                "retryCount": r1,
                "elapsedMs": elapsed,
                "status": status.value,
                "errorMessage": smsg,
            })
        else:
            logger.info("SEARCH success", {
                "step": "SEARCH",
                "contract_number": code,
                "contract_id": c_id,
                "httpStatus": 200,
                "retryCount": r1,
                "elapsedMs": elapsed,
            })

            step_start = time.perf_counter()
            logger.info("CONTRACT_INFO start", {"step": "CONTRACT_INFO", "contract_number": code, "contract_id": c_id})
            coop_id, r2, icode, imsg = clm.get_cooperation_id(c_id)
            elapsed2 = int((time.perf_counter() - step_start) * 1000)
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
                # 在 CONTRACT_INFO 失败时，将错误响应信息写入结果的 cooperation_id 列
                logger.warn("CONTRACT_INFO failed", {
                    "step": "CONTRACT_INFO",
                    "contract_number": code,
                    "contract_id": c_id,
                    "httpStatus": icode,
                    "retryCount": r2,
                    "elapsedMs": elapsed2,
                    "status": status.value,
                    "errorMessage": imsg,
                })
            else:
                logger.info("CONTRACT_INFO success", {
                    "step": "CONTRACT_INFO",
                    "contract_number": code,
                    "contract_id": c_id,
                    "cooperation_id": coop_id,
                    "httpStatus": 200,
                    "retryCount": r2,
                    "elapsedMs": elapsed2,
                })

                step_start = time.perf_counter()
                logger.info("COOP_INFO start", {"step": "COOP_INFO", "contract_number": code, "cooperation_id": coop_id})
                chat_id, r3, ocode, omsg = clm.get_open_chat_id(coop_id)
                elapsed3 = int((time.perf_counter() - step_start) * 1000)
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
                    # 在 COOP_INFO 失败时，将错误响应信息写入结果的 openChatId 列
                    logger.warn("COOP_INFO failed", {
                        "step": "COOP_INFO",
                        "contract_number": code,
                        "cooperation_id": coop_id,
                        "httpStatus": ocode,
                        "retryCount": r3,
                        "elapsedMs": elapsed3,
                        "status": status.value,
                        "errorMessage": omsg,
                    })
                else:
                    status = Status.SUCCESS
                    err_code = None
                    err_msg = None
                    logger.info("COOP_INFO success", {
                        "step": "COOP_INFO",
                        "contract_number": code,
                        "cooperation_id": coop_id,
                        "openChatId": chat_id,
                        "httpStatus": 200,
                        "retryCount": r3,
                        "elapsedMs": elapsed3,
                    })

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
        progress = round(done * 100.0 / max(1, total), 2)
        logger.info("progress", {
            "progressPercent": progress,
            "success_count": succ,
            "fail_count": fail,
            "ETA_s": int(eta),
            "done": done,
            "total": total,
        })

    merged_map: Dict[str, ResultRow] = dict(existing_map)
    for row in results:
        merged_map[row.contract_number] = row

    out_rows: List[ResultRow] = []
    for cn in existing_order:
        if cn in merged_map:
            out_rows.append(merged_map[cn])

    new_additions = [r.contract_number for r in results if r.contract_number not in existing_order]
    for cn in new_additions:
        out_rows.append(merged_map[cn])

    if not existing_order and not results:
        out_rows = []

    write_results(output_excel, out_rows)
    logger.info("batch_end", {"total": total, "success_count": succ, "fail_count": fail, "output": output_excel})
