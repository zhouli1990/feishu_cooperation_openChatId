from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


class JsonLogger:
    """简单的JSON日志器：同时输出到控制台与文件（逐行JSON）。"""

    def __init__(self, file_path: str, module: str = "app", level: str = "INFO", context: Optional[Dict[str, Any]] = None) -> None:
        self.file_path = file_path
        self.module = module
        self.level = (level or "INFO").upper()
        self._level_map = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}
        self._min_level = self._level_map.get(self.level, 20)
        self.context: Dict[str, Any] = dict(context or {})
        # 确保日志目录存在
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_trace_id() -> str:
        return uuid.uuid4().hex

    def with_context(self, ctx: Dict[str, Any]) -> "JsonLogger":
        merged = dict(self.context)
        merged.update(ctx or {})
        return JsonLogger(self.file_path, module=self.module, level=self.level, context=merged)

    def _should_log(self, msg_level: str) -> bool:
        lv = self._level_map.get((msg_level or "INFO").upper(), 20)
        return lv >= self._min_level

    def _emit(self, level: str, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if not self._should_log(level):
            return
        rec: Dict[str, Any] = {
            "ts": _now_iso(),
            "level": level,
            "module": self.module,
            "message": msg,
        }
        if self.context:
            rec.update(self.context)
        if extra:
            rec.update(extra)
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        # 控制台
        print(line)
        # 文件落盘
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit("DEBUG", msg, extra)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit("INFO", msg, extra)

    def warn(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit("WARN", msg, extra)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit("ERROR", msg, extra)
