from __future__ import annotations

from typing import List


def read_contract_numbers(path: str) -> List[str]:
    result: List[str] = []
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s in seen:
                continue
            seen.add(s)
            result.append(s)
    return result
