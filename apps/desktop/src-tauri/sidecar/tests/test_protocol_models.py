from __future__ import annotations

import pytest
from pydantic import ValidationError

from sidecar.protocol_models import PROTOCOL_VERSION, JSONRPCRequest


def test_protocol_version_matches_schema() -> None:
    assert PROTOCOL_VERSION == "1.6.0"


def test_request_accepts_valid_payload() -> None:
    request = JSONRPCRequest.model_validate(
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {"echo": "hi"}}
    )
    assert request.method == "ping"
    assert request.id == 1
    assert request.params == {"echo": "hi"}


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        JSONRPCRequest.model_validate(
            {"jsonrpc": "2.0", "method": "ping", "unexpected": True}
        )


def test_request_requires_jsonrpc_2() -> None:
    with pytest.raises(ValidationError):
        JSONRPCRequest.model_validate({"jsonrpc": "1.0", "method": "ping"})
