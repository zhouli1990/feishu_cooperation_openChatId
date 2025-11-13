from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .models import Status


def _merge_defaults(user: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(defaults)
    for k, v in user.items() if user else []:
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_defaults(v, out[k])
        else:
            out[k] = v
    return out


def _ensure_dirs(cfg: Dict[str, Any]) -> None:
    files = cfg.get("files") or {}
    out_excel = files.get("output_excel")
    log_file = files.get("log_file")
    if out_excel:
        Path(out_excel).parent.mkdir(parents=True, exist_ok=True)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)


def _validate(cfg: Dict[str, Any]) -> None:
    rl = cfg.get("rate_limit") or {}
    rq = [
        rl.get("global_qpm"),
        rl.get("contract_search_qpm"),
        rl.get("contract_info_qpm"),
        rl.get("cooperation_info_qpm"),
    ]
    if any((not isinstance(x, int) or x <= 0) for x in rq):
        raise ValueError("rate_limit.* 必须为正整数")
    if not isinstance(rl.get("concurrency"), int) or rl.get("concurrency") < 1:
        raise ValueError("concurrency 必须为 >=1 的整数")

    rt = cfg.get("retry") or {}
    if not isinstance(rt.get("timeout_ms"), int) or rt.get("timeout_ms") <= 0:
        raise ValueError("timeout_ms 必须为正整数")
    for key in ("max_retries", "base_delay_ms", "max_delay_ms"):
        if not isinstance(rt.get(key), int) or rt.get(key) < 0:
            raise ValueError(f"{key} 必须为非负整数")
    if rt.get("max_delay_ms") < rt.get("base_delay_ms"):
        raise ValueError("max_delay_ms 需 >= base_delay_ms")
    if not isinstance(rt.get("jitter"), (int, float)) or not (0 <= float(rt.get("jitter")) <= 1):
        raise ValueError("jitter 需在 [0,1] 范围内")

    skip_statuses = rt.get("skip_result_statuses")
    if not isinstance(skip_statuses, list):
        raise ValueError("skip_result_statuses 必须为字符串列表")
    invalid: List[str] = []
    for item in skip_statuses:
        if not isinstance(item, str):
            raise ValueError("skip_result_statuses 中的元素必须为字符串")
        try:
            Status(item)
        except ValueError:
            invalid.append(item)
    if invalid:
        raise ValueError(f"skip_result_statuses 存在无效状态: {', '.join(invalid)}")

    files = cfg.get("files") or {}
    for key in ("input_txt", "output_excel", "log_file"):
        if not isinstance(files.get(key), str) or not files.get(key):
            raise ValueError(f"files.{key} 不能为空")

    log_cfg = cfg.get("log") or {}
    lvl = log_cfg.get("level") or "INFO"
    if not isinstance(lvl, str) or lvl.upper() not in ("DEBUG", "INFO", "WARN", "ERROR"):
        raise ValueError("log.level 必须为 DEBUG/INFO/WARN/ERROR 之一")


def load_config(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"未找到配置文件: {p}")

    try:
        import yaml  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("缺少依赖 pyyaml，请先安装: pip install pyyaml") from e

    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    defaults: Dict[str, Any] = {
        "files": {
            "input_txt": "./input/contracts.txt",
            "output_excel": "./output/contract_openChatId.xlsx",
            "log_file": "./logs/run.log",
        },
        "auth": {
            "app_id": "",
            "app_secret": "",
            "cookies": {"session": ""},
        },
        "rate_limit": {
            "global_qpm": 60,
            "contract_search_qpm": 60,
            "contract_info_qpm": 60,
            "cooperation_info_qpm": 60,
            "concurrency": 1,
        },
        "retry": {
            "timeout_ms": 8000,
            "max_retries": 3,
            "base_delay_ms": 500,
            "max_delay_ms": 10000,
            "jitter": 0.2,
            "skip_result_statuses": [
                Status.SUCCESS.value,
                Status.NOT_FOUND_CONTRACT.value,
                Status.NO_COOPERATION.value,
                Status.NO_CHAT_GROUP.value,
            ],
        },
        "log": {
            "level": "DEBUG",
        },
    }

    cfg = _merge_defaults(data, defaults)
    _ensure_dirs(cfg)
    _validate(cfg)
    return cfg
