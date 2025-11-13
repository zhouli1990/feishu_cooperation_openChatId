from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Status(str, Enum):
    SUCCESS = "SUCCESS"
    NOT_FOUND_CONTRACT = "NOT_FOUND_CONTRACT"
    NO_COOPERATION = "NO_COOPERATION"
    NO_CHAT_GROUP = "NO_CHAT_GROUP"
    AUTH_FAILED = "AUTH_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RETRY_EXCEEDED = "RETRY_EXCEEDED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class ResultRow:
    contract_number: str
    contract_id: Optional[str]
    cooperation_id: Optional[str]
    openChatId: Optional[str]
    status: Status
    error_code: Optional[str]
    error_message: Optional[str]
