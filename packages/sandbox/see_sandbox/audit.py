from __future__ import annotations

import hashlib


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
