from __future__ import annotations

from pathlib import Path
from typing import Iterable

from openpyxl import Workbook

from ..models import ResultRow


def write_results(path: str, rows: Iterable[ResultRow]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    headers = [
        "contract_number",
        "contract_id",
        "cooperation_id",
        "openChatId",
        "status",
        "error_code",
        "error_message",
    ]
    ws.append(headers)
    for r in rows:
        ws.append([
            r.contract_number or "",
            r.contract_id or "",
            r.cooperation_id or "",
            r.openChatId or "",
            r.status.value if hasattr(r.status, 'value') else str(r.status),
            r.error_code or "",
            r.error_message or "",
        ])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
