from __future__ import annotations

from agent_core import TraceRecorder


def test_trace_redacts_content_and_secrets() -> None:
    recorder = TraceRecorder()
    recorder.begin_turn()
    event = recorder.record(
        "tool",
        {
            "tool": "web_search",
            "apiKey": "sk-secret-value-12345",
            "content": "texte sensible",
            "nested": {"result": "très long", "status": "ok"},
        },
    )
    payload = event.to_dict()
    assert payload["data"]["tool"] == "web_search"
    assert payload["data"]["apiKey"] == "[REDACTED]"
    assert payload["data"]["content"].endswith("chars]")
    assert payload["data"]["nested"]["result"].endswith("chars]")
    assert payload["data"]["nested"]["status"] == "ok"


def test_trace_export_is_json() -> None:
    recorder = TraceRecorder()
    recorder.begin_turn()
    recorder.record("response", {"status": "ok"}, role="interviewer")
    exported = recorder.export()
    assert exported["turn"] == 1
    assert exported["events"][0]["role"] == "interviewer"
    assert "apiKey" not in recorder.export_json()
