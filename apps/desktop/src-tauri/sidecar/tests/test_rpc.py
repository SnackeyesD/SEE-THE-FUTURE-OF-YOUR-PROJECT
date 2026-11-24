from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

SIDECAR_DIR = Path(__file__).resolve().parents[1]

SIMULATION_SCENARIO: dict[str, Any] = {
    "name": "Test sidecar",
    "horizonMonths": 2,
    "assumptions": {
        "initial_cash": {"value": 0},
        "unit_price": {"value": 10},
        "unit_cost": {"value": 5},
        "fixed_costs_monthly": {"value": 0},
        "demand_mean_monthly": {"value": 10},
        "demand_cv": {"value": 0},
        "loss_rate": {"value": 0},
        "target_stock_months": {"value": 0},
        "reorder_lead_time_months": {"value": 1},
        "initial_stock": {"value": 100},
        "tax_rate": {"value": 0},
    },
}


class SidecarProcess:
    def __init__(self, data_dir: Path | None = None) -> None:
        environment = os.environ.copy()
        if data_dir is not None:
            environment["SEE_DATA_DIR"] = str(data_dir)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "sidecar"],
            cwd=SIDECAR_DIR,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)

    def send_raw(self, raw: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(raw)
        self.proc.stdin.flush()

    def send(self, payload: dict[str, Any]) -> None:
        self.send_raw(json.dumps(payload) + "\n")

    def read_json(self, timeout: float = 30.0) -> dict[str, Any]:
        line = self._lines.get(timeout=timeout)
        return json.loads(line)

    def call(self, method: str, params: dict[str, Any] | None = None,
             request_id: int = 1) -> dict[str, Any]:
        self.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        return self.read_json()

    def collect(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: int = 1,
        timeout: float = 30.0,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        notifications: list[dict[str, Any]] = []
        while True:
            message = self.read_json(timeout=timeout)
            if message.get("id") == request_id and (
                "result" in message or "error" in message
            ):
                return notifications, message
            notifications.append(message)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)


@pytest.fixture
def sidecar(tmp_path: Path) -> SidecarProcess:
    process = SidecarProcess(tmp_path / "data")
    try:
        yield process
    finally:
        process.close()


def test_ping_returns_pong_and_echo(sidecar: SidecarProcess) -> None:
    response = sidecar.call("ping", {"echo": "hello"}, request_id=7)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 7
    assert response["result"]["pong"] is True
    assert response["result"]["echo"] == "hello"
    assert isinstance(response["result"]["timestamp"], str)


def test_health_exposes_versions(sidecar: SidecarProcess) -> None:
    response = sidecar.call("health")
    result = response["result"]
    assert result["status"] == "ok"
    assert result["protocolVersion"] == "1.15.0"
    assert isinstance(result["pid"], int)
    assert result["sidecarVersion"]


def test_benchmark_lookup_returns_signed_record(sidecar: SidecarProcess) -> None:
    response = sidecar.call(
        "benchmark.lookup",
        {
            "indicator": "unit_price",
            "country": "CG",
            "region": "Brazzaville",
            "sector": "retail",
            "subsector": "alimentation_generale",
        },
        request_id=21,
    )
    record = response["result"]["record"]
    assert response["result"]["found"] is True
    assert record["packId"] == "cg-brazzaville-retail-2026.1"
    assert record["keyId"] == "seefuture-benchmark-2026"


def test_benchmark_pack_list_exposes_bundled_packs(sidecar: SidecarProcess) -> None:
    response = sidecar.call("benchmark.pack.list", request_id=22)
    packs = response["result"]["packs"]
    assert response["result"]["errors"] == []
    assert {pack["packId"] for pack in packs} == {
        "cg-brazzaville-retail-2026.1",
        "cf-bangui-retail-2026.1",
    }


def test_unknown_method_returns_method_not_found(sidecar: SidecarProcess) -> None:
    response = sidecar.call("does_not_exist")
    assert response["error"]["code"] == -32601
    assert "does_not_exist" in response["error"]["message"]


def test_parse_error_returns_minus_32700(sidecar: SidecarProcess) -> None:
    sidecar.send_raw("this is not json\n")
    response = sidecar.read_json()
    assert response["error"]["code"] == -32700
    assert response["id"] is None


def test_invalid_request_returns_minus_32600(sidecar: SidecarProcess) -> None:
    sidecar.send({"id": 3, "method": "ping"})
    response = sidecar.read_json()
    assert response["error"]["code"] == -32600
    assert response["id"] == 3


def test_notification_gets_no_response(sidecar: SidecarProcess) -> None:
    sidecar.send(
        {"jsonrpc": "2.0", "method": "log", "params": {"level": "info", "message": "hi"}}
    )
    response = sidecar.call("ping", request_id=42)
    assert response["id"] == 42


def test_shutdown_stops_the_process(sidecar: SidecarProcess) -> None:
    response = sidecar.call("shutdown")
    assert response["result"]["ok"] is True
    assert sidecar.proc.wait(timeout=5) == 0


def test_simulate_returns_deterministic_aggregates(sidecar: SidecarProcess) -> None:
    response = sidecar.call(
        "simulate",
        {"scenario": SIMULATION_SCENARIO, "config": {"runs": 100, "seed": 3}},
        request_id=11,
    )
    assert response["id"] == 11
    result = response["result"]
    assert result["runs"] == 100
    assert result["seed"] == 3
    assert result["metrics"]["meanProfit"] == pytest.approx(100.0)
    assert sum(bin["count"] for bin in result["histogram"]["bins"]) == 100
    assert len(result["monthly"]["values"]) == 2
    assert result["breakEven"]["unitMargin"] == pytest.approx(5.0)


def test_simulate_rejects_invalid_scenario(sidecar: SidecarProcess) -> None:
    response = sidecar.call("simulate", {"scenario": {"name": "Sans hypothèses"}})
    assert response["error"]["code"] == -32602
    assert "requise" in response["error"]["message"]


def test_simulate_maps_unexpected_engine_error_to_internal_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import engine

    from sidecar import rpc

    def explode(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("secret interne à ne pas exposer")

    monkeypatch.setattr(engine, "simulate", explode)
    context = rpc.RequestContext(lambda _method, _params: None)

    with caplog.at_level(logging.ERROR, logger="see.sidecar"):
        with pytest.raises(rpc.RpcError) as caught:
            rpc.simulate({"scenario": SIMULATION_SCENARIO, "config": {"runs": 1}}, context)

    assert caught.value.code == rpc.INTERNAL_ERROR
    assert "simulation" in caught.value.message
    assert "secret interne" not in caught.value.message
    assert any(record.exc_info for record in caplog.records)


def test_simulate_emits_progress_notifications(sidecar: SidecarProcess) -> None:
    notifications, response = sidecar.collect(
        "simulate",
        {
            "scenario": SIMULATION_SCENARIO,
            "config": {"runs": 100, "seed": 1, "batchSize": 25},
            "progress": True,
        },
        request_id=12,
    )
    assert "result" in response
    assert notifications
    assert all(item["method"] == "simulate.progress" for item in notifications)
    values = [item["params"]["progress"] for item in notifications]
    assert values[0] == 0.0
    assert values[-1] == 1.0
    assert values == sorted(values)


def test_project_workflow_persists_brief_scenario_and_run(sidecar: SidecarProcess) -> None:
    created = sidecar.call("project.create", {"name": "Parcours MVP"}, request_id=30)
    project_id = created["result"]["project"]["id"]

    brief = sidecar.call(
        "project.brief.save",
        {
            "projectId": project_id,
            "content": {
                "problem": "Approvisionnement irrégulier",
                "customer": "Détaillants",
                "valueProposition": "Stock fiable",
                "revenueModel": "Marge sur vente",
                "costStructure": "Achat et logistique",
                "geography": "Abidjan",
            },
            "status": "validated",
        },
        request_id=31,
    )
    assert brief["result"]["brief"]["status"] == "validated"
    assert brief["result"]["brief"]["version"] == 1

    saved = sidecar.call(
        "project.scenario.save",
        {
            "projectId": project_id,
            "name": "Scénario de base",
            "scenario": SIMULATION_SCENARIO,
        },
        request_id=32,
    )
    assert saved["result"]["scenario"]["name"] == "Scénario de base"

    notifications, response = sidecar.collect(
        "project.simulate",
        {
            "projectId": project_id,
            "config": {"runs": 100, "seed": 5, "batchSize": 25},
            "progress": True,
        },
        request_id=33,
    )
    assert "result" in response
    assert notifications[0]["method"] == "simulate.progress"
    result = response["result"]
    assert result["run"]["runs"] == 100
    assert result["run"]["scenarioId"] == saved["result"]["scenario"]["id"]
    assert result["result"]["metrics"]["meanProfit"] == pytest.approx(100.0)

    data = sidecar.call("project.data", {"projectId": project_id}, request_id=34)
    assert data["result"]["brief"]["status"] == "validated"
    assert data["result"]["scenario"]["id"] == saved["result"]["scenario"]["id"]
    assert data["result"]["run"]["id"] == result["run"]["id"]
    assert data["result"]["run"]["result"]["runs"] == 100

    session = sidecar.call("agent.state", {"projectId": project_id}, request_id=35)
    assert session["result"]["session"]["state"] == "results_ready"


def test_project_workflow_rejects_incomplete_brief(sidecar: SidecarProcess) -> None:
    created = sidecar.call("project.create", {"name": "Brief incomplet"}, request_id=40)
    project_id = created["result"]["project"]["id"]
    response = sidecar.call(
        "project.brief.save",
        {
            "projectId": project_id,
            "content": {"problem": "Manque le reste"},
            "status": "validated",
        },
        request_id=41,
    )
    assert response["error"]["code"] == -32602
    assert "customer" in response["error"]["message"]


def test_project_lifecycle(sidecar: SidecarProcess) -> None:
    created = sidecar.call("project.create", {"name": "Projet sidecar"}, request_id=20)
    project = created["result"]["project"]
    project_id = project["id"]
    assert project["status"] == "active"

    listed = sidecar.call("project.list", request_id=21)
    assert [item["id"] for item in listed["result"]["projects"]] == [project_id]

    renamed = sidecar.call(
        "project.rename", {"projectId": project_id, "name": "Renommé"}, request_id=22
    )
    assert renamed["result"]["project"]["name"] == "Renommé"

    duplicated = sidecar.call("project.duplicate", {"projectId": project_id}, request_id=23)
    duplicate = duplicated["result"]["project"]
    assert duplicate["name"] == "Renommé (copie)"

    sidecar.call("project.archive", {"projectId": project_id}, request_id=24)
    active = sidecar.call("project.list", request_id=25)["result"]["projects"]
    assert project_id not in [item["id"] for item in active]
    archived = sidecar.call(
        "project.list", {"includeArchived": True}, request_id=26
    )["result"]["projects"]
    assert project_id in [item["id"] for item in archived]

    sidecar.call("project.restore", {"projectId": project_id}, request_id=27)
    sidecar.call("project.trash", {"projectId": project_id}, request_id=28)
    refused = sidecar.call("project.open", {"projectId": project_id}, request_id=29)
    assert refused["error"]["code"] == -32602
    sidecar.call("project.restore", {"projectId": project_id}, request_id=30)

    deleted = sidecar.call("project.delete", {"projectId": project_id}, request_id=31)
    assert deleted["result"]["deleted"] is True
    missing = sidecar.call("project.open", {"projectId": project_id}, request_id=32)
    assert missing["error"]["code"] == -32001


def test_project_create_rejects_invalid_params(sidecar: SidecarProcess) -> None:
    response = sidecar.call("project.create", {"description": "sans nom"}, request_id=33)
    assert response["error"]["code"] == -32602


def test_project_export_import_and_integrity(
    sidecar: SidecarProcess, tmp_path: Path
) -> None:
    project = sidecar.call("project.create", {"name": "Exportable"}, request_id=40)["result"][
        "project"
    ]
    archive = tmp_path / "exportable.simproj"
    exported = sidecar.call(
        "project.export",
        {"projectId": project["id"], "destination": str(archive)},
        request_id=41,
    )["result"]
    assert archive.is_file()
    assert exported["bytes"] == archive.stat().st_size
    assert len(exported["checksum"]) == 64

    imported = sidecar.call(
        "project.import", {"source": str(archive), "name": "Importé"}, request_id=42
    )["result"]["project"]
    assert imported["name"] == "Importé"
    assert imported["id"] != project["id"]

    size = sidecar.call("project.size", {"projectId": imported["id"]}, request_id=43)[
        "result"
    ]
    assert size["databaseBytes"] > 0
    assert size["totalBytes"] >= size["databaseBytes"]

    integrity = sidecar.call("integrity.check", request_id=44)["result"]
    assert integrity == {"ok": True, "message": "ok"}

    backup_dir = tmp_path / "backups"
    backup = sidecar.call(
        "storage.backup", {"destination": str(backup_dir)}, request_id=45
    )["result"]
    assert Path(backup["path"]).is_file()
    assert Path(backup["path"]).parent == backup_dir

def test_provider_profiles_roles_and_budget(sidecar: SidecarProcess) -> None:
    catalog = sidecar.call("provider.catalog", request_id=50)["result"]
    assert catalog["capabilitiesVersion"]
    assert any(item["id"] == "openai" for item in catalog["providers"])

    project = sidecar.call("project.create", {"name": "Fournisseurs"}, request_id=51)["result"][
        "project"
    ]
    profile = sidecar.call(
        "provider.profile.save",
        {
            "projectId": project["id"],
            "name": "OpenAI test",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "keychainRef": "seefuture:test",
        },
        request_id=52,
    )["result"]["profile"]
    assert profile["keychainRef"] == "seefuture:test"
    assert profile["capabilities"]["nativeTools"] is True

    assignment = sidecar.call(
        "provider.role.set",
        {
            "projectId": project["id"],
            "role": "modeler",
            "providerProfileId": profile["id"],
            "model": "gpt-4o-mini",
        },
        request_id=53,
    )["result"]["assignment"]
    assert assignment["role"] == "modeler"
    assert sidecar.call(
        "provider.role.list", {"projectId": project["id"]}, request_id=54
    )["result"]["assignments"][0]["id"] == assignment["id"]

    budget = sidecar.call(
        "provider.budget.set",
        {"projectId": project["id"], "limitMicros": 5_000_000},
        request_id=55,
    )["result"]
    assert budget["limitMicros"] == 5_000_000
    assert budget["spentMicros"] == 0

    usage = sidecar.call(
        "provider.usage", {"projectId": project["id"]}, request_id=56
    )["result"]
    assert usage["entries"] == []

    invalid = sidecar.call("provider.role.set", {"projectId": project["id"]}, request_id=57)
    assert invalid["error"]["code"] == -32602

    deleted = sidecar.call(
        "provider.profile.delete", {"profileId": profile["id"]}, request_id=58
    )["result"]
    assert deleted["deleted"] is True
    assert sidecar.call(
        "provider.role.list", {"projectId": project["id"]}, request_id=59
    )["result"]["assignments"] == []

def test_provider_chat_streams_and_budget_blocks(sidecar: SidecarProcess) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            chunks = [
                b'data: {"choices":[{"delta":{"content":"Bonjour"}}]}\n\n',
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
                b'"usage":{"prompt_tokens":5,"completion_tokens":1}}\n\n',
                b"data: [DONE]\n\n",
            ]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            for chunk in chunks:
                self.wfile.write(chunk)
                self.wfile.flush()

        def log_message(self, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project = sidecar.call("project.create", {"name": "Chat local"}, request_id=70)["result"][
            "project"
        ]
        profile = sidecar.call(
            "provider.profile.save",
            {
                "projectId": project["id"],
                "name": "Faux OpenAI",
                "provider": "openai-compatible",
                "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "gpt-4o-mini",
            },
            request_id=71,
        )["result"]["profile"]
        params = {
            "projectId": project["id"],
            "profile": profile,
            "apiKey": "test-key",
            "request": {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Bonjour"}],
            },
        }
        result = sidecar.call("provider.chat", params, request_id=72)["result"]
        assert result["text"] == "Bonjour"
        assert result["usage"]["inputTokens"] == 5
        assert result["usage"]["costMicros"] > 0

        sidecar.call(
            "provider.budget.set",
            {"projectId": project["id"], "limitMicros": 1},
            request_id=73,
        )
        blocked = sidecar.call("provider.chat", params, request_id=74)
        assert blocked["error"]["code"] == -32004
        assert blocked["error"]["data"]["limitMicros"] == 1

        usage = sidecar.call(
            "provider.usage", {"projectId": project["id"]}, request_id=75
        )["result"]
        assert len(usage["entries"]) == 1
        assert usage["inputTokens"] == 5
    finally:
        server.shutdown()
        server.server_close()

def test_agent_state_permissions_tools_and_prepare(sidecar: SidecarProcess) -> None:
    project = sidecar.call("project.create", {"name": "Agent"}, request_id=80)["result"][
        "project"
    ]
    state = sidecar.call("agent.state", {"projectId": project["id"]}, request_id=81)["result"]
    assert state["session"]["state"] == "idea"
    assert state["session"]["projectId"] == project["id"]

    started = sidecar.call("agent.start", {"projectId": project["id"]}, request_id=82)
    assert started["result"]["session"]["state"] == "interviewing"

    missing = sidecar.call("agent.prepare", {"projectId": project["id"]}, request_id=83)
    assert missing["error"]["code"] == -32005
    assert missing["error"]["data"]["code"] == "agent_configuration"

    profile = sidecar.call(
        "provider.profile.save",
        {
            "projectId": project["id"],
            "name": "Agent local",
            "provider": "ollama",
            "baseUrl": "http://127.0.0.1:11434",
            "model": "qwen",
        },
        request_id=84,
    )["result"]["profile"]
    sidecar.call(
        "provider.role.set",
        {
            "projectId": project["id"],
            "role": "interviewer",
            "providerProfileId": profile["id"],
            "model": "qwen",
        },
        request_id=85,
    )
    prepared = sidecar.call("agent.prepare", {"projectId": project["id"]}, request_id=86)[
        "result"
    ]
    assert prepared["role"] == "interviewer"
    assert prepared["state"] == "interviewing"
    assert prepared["profile"]["id"] == profile["id"]

    permissions = sidecar.call(
        "agent.permission.list", {"projectId": project["id"]}, request_id=87
    )["result"]
    assert permissions["defaults"]["web_search"] == "ask"
    assert "run_custom_script" in permissions["alwaysAsk"]
    changed = sidecar.call(
        "agent.permission.set",
        {
            "projectId": project["id"],
            "tool": "web_search",
            "decision": "deny",
            "reason": "test",
        },
        request_id=88,
    )["result"]
    assert changed["permission"]["decision"] == "deny"
    assert changed["events"][0]["actor"] == "user"

    tools = sidecar.call("agent.tools", request_id=89)["result"]["tools"]
    custom = next(item for item in tools if item["name"] == "run_custom_script")
    assert custom["alwaysAsk"] is True

    trace = sidecar.call("agent.trace", {"projectId": project["id"]}, request_id=90)[
        "result"
    ]
    assert trace["count"] == 0
    reset = sidecar.call("agent.reset", {"projectId": project["id"]}, request_id=91)
    assert reset["result"]["session"]["state"] == "idea"


def test_agent_turn_streams_text_and_records_trace(sidecar: SidecarProcess) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            chunks = [
                b'data: {"choices":[{"delta":{"content":"Bonjour"}}]}\n\n',
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
                b'"usage":{"prompt_tokens":5,"completion_tokens":1}}\n\n',
                b"data: [DONE]\n\n",
            ]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            for chunk in chunks:
                self.wfile.write(chunk)
                self.wfile.flush()

        def log_message(self, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project = sidecar.call("project.create", {"name": "Agent chat"}, request_id=100)[
            "result"
        ]["project"]
        profile = sidecar.call(
            "provider.profile.save",
            {
                "projectId": project["id"],
                "name": "Faux agent",
                "provider": "openai-compatible",
                "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "gpt-4o-mini",
            },
            request_id=101,
        )["result"]["profile"]
        sidecar.call(
            "provider.role.set",
            {
                "projectId": project["id"],
                "role": "interviewer",
                "providerProfileId": profile["id"],
                "model": "gpt-4o-mini",
            },
            request_id=102,
        )
        prepared = sidecar.call("agent.prepare", {"projectId": project["id"]}, request_id=103)[
            "result"
        ]
        result = sidecar.call(
            "agent.turn",
            {
                "projectId": project["id"],
                "profile": prepared["profile"],
                "role": prepared["role"],
                "apiKey": "test-key",
                "message": "Bonjour",
            },
            request_id=104,
        )["result"]
        assert result["status"] == "text"
        assert result["text"] == "Bonjour"
        assert result["session"]["thread"][-1]["content"] == "Bonjour"
        assert result["usage"]["inputTokens"] == 5
        trace = sidecar.call("agent.trace", {"projectId": project["id"]}, request_id=105)[
            "result"
        ]
        assert trace["count"] >= 2
        assert trace["events"][0]["event"]["kind"] in {"request", "response"}
    finally:
        server.shutdown()
        server.server_close()


def test_agent_benchmark_query_uses_brief_and_recovers_from_free_text(
    sidecar: SidecarProcess,
) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    requests: list[dict[str, Any]] = []

    def sse(*chunks: dict[str, Any]) -> bytes:
        lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
        lines.append("data: [DONE]\n\n")
        return "".join(lines).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            requests.append(json.loads(self.rfile.read(length)))
            if len(requests) == 1:
                calls = [
                    {
                        "index": 0,
                        "id": "brief_1",
                        "type": "function",
                        "function": {
                            "name": "update_brief",
                            "arguments": json.dumps(
                                {
                                    "problem": "Livrer des repas",
                                    "customer": "Bureaux du centre-ville",
                                    "valueProposition": "Livraison rapide",
                                    "revenueModel": "Marge sur les repas",
                                    "costStructure": "Achats et loyer",
                                    "geography": "Congo",
                                }
                            ),
                        },
                    },
                    {
                        "index": 1,
                        "id": "benchmark_1",
                        "type": "function",
                        "function": {
                            "name": "get_benchmark",
                            "arguments": json.dumps(
                                {
                                    "indicator": "fixed_costs_monthly",
                                    "country": "Congo",
                                }
                            ),
                        },
                    },
                    {
                        "index": 2,
                        "id": "benchmark_2",
                        "type": "function",
                        "function": {
                            "name": "get_benchmark",
                            "arguments": json.dumps(
                                {
                                    "indicator": "loyer commercial mensuel",
                                    "country": "Congo",
                                }
                            ),
                        },
                    },
                ]
                payload = sse(
                    {"choices": [{"delta": {"tool_calls": calls}}]},
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                )
            else:
                payload = sse(
                    {"choices": [{"delta": {"content": "Benchmark vérifié."}}]},
                    {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()

        def log_message(self, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project = sidecar.call("project.create", {"name": "Agent benchmark"}, request_id=110)[
            "result"
        ]["project"]
        profile = sidecar.call(
            "provider.profile.save",
            {
                "projectId": project["id"],
                "name": "Faux benchmark",
                "provider": "openai-compatible",
                "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "gpt-4o-mini",
            },
            request_id=111,
        )["result"]["profile"]
        sidecar.call(
            "provider.role.set",
            {
                "projectId": project["id"],
                "role": "interviewer",
                "providerProfileId": profile["id"],
                "model": "gpt-4o-mini",
            },
            request_id=112,
        )
        prepared = sidecar.call("agent.prepare", {"projectId": project["id"]}, request_id=113)[
            "result"
        ]
        response = sidecar.call(
            "agent.turn",
            {
                "projectId": project["id"],
                "profile": prepared["profile"],
                "role": prepared["role"],
                "apiKey": "test-key",
                "message": "Je valide le brief.",
            },
            request_id=114,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "error" not in response
    result = response["result"]
    assert result["status"] == "text"
    assert result["text"] == "Benchmark vérifié."
    assert "fixed_costs_monthly" in requests[0]["messages"][0]["content"]
    events = [
        event for event in result["toolEvents"] if event["tool"] == "get_benchmark"
    ]
    assert len(events) == 2
    canonical, free_text = events
    assert canonical["ok"] is True
    assert canonical["result"]["found"] is True
    assert canonical["result"]["record"]["country"] == "CG"
    assert free_text["ok"] is True
    assert free_text["result"]["found"] is False
    assert "loyer_commercial_mensuel" in free_text["result"]["reason"]
    assert "fixed_costs_monthly" in free_text["result"]["reason"]


def test_sandbox_analysis_audit_and_export(sidecar: SidecarProcess, tmp_path: Path) -> None:
    project = sidecar.call("project.create", {"name": "Sandbox"}, request_id=120)["result"][
        "project"
    ]
    code = "def main(data):\n    return {'metrics': [{'label': 'x', 'value': 1}]}\n"
    analysis = sidecar.call("sandbox.analyze", {"code": code}, request_id=121)["result"][
        "analysis"
    ]
    assert analysis["ok"] is True
    assert len(analysis["codeHash"]) == 64
    assert "numpy" in analysis["allowedImports"]

    recorded = sidecar.call(
        "sandbox.audit.record",
        {
            "projectId": project["id"],
            "code": code,
            "codeHash": analysis["codeHash"],
            "purpose": "test",
            "decision": "approved",
            "status": "succeeded",
            "result": {"metrics": [{"label": "x", "value": 1}]},
            "durationMs": 12.0,
        },
        request_id=122,
    )["result"]["record"]
    assert recorded["codeHash"] == analysis["codeHash"]
    assert recorded["status"] == "succeeded"

    listed = sidecar.call(
        "sandbox.audit.list", {"projectId": project["id"]}, request_id=123
    )["result"]
    assert listed["count"] == 1
    assert listed["records"][0]["id"] == recorded["id"]

    exported = sidecar.call(
        "sandbox.audit.export", {"projectId": project["id"]}, request_id=124
    )["result"]
    assert exported["count"] == 1
    assert Path(exported["path"]).is_file()

    refused = sidecar.call(
        "sandbox.audit.record",
        {
            "projectId": project["id"],
            "code": "import os\n\ndef main(data):\n    return {}\n",
            "codeHash": "0" * 64,
            "decision": "approved",
            "status": "succeeded",
            "result": {"metrics": []},
        },
        request_id=125,
    )
    assert refused["error"]["code"] == -32602



# ---------------------------------------------------------------------------
# Phase 06 — flux, ordre, concurrence et annulation
# ---------------------------------------------------------------------------

SLOW_CONFIG: dict[str, Any] = {"runs": 120_000, "batchSize": 512}


def _create_project(sidecar: SidecarProcess, name: str = "Phase 06") -> str:
    # ``collect`` tolère le démarrage à froid du sidecar (imports numpy/engine)
    # qui peut dépasser le délai par défaut de 5 s sur une machine chargée.
    _, created = sidecar.collect(
        "project.create", {"name": name}, request_id=900, timeout=30.0
    )
    return created["result"]["project"]["id"]


def _is_terminal(message: dict[str, Any]) -> bool:
    return message.get("method") in {
        "simulation.done",
        "simulation.cancelled",
        "simulation.error",
    }


def _read_until(
    sidecar: SidecarProcess,
    predicate: Any,
    *,
    timeout: float = 30.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("événement attendu non reçu")
        message = sidecar.read_json(timeout=remaining)
        if message.get("method") is not None:
            messages.append(message)
            if predicate(message):
                return messages, message


def _drain(sidecar: SidecarProcess, duration: float = 0.3) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    deadline = time.monotonic() + duration
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return messages
        try:
            messages.append(sidecar.read_json(timeout=remaining))
        except queue.Empty:
            return messages


def test_start_is_fast_partials_are_ordered_and_draft_is_not_persisted(
    sidecar: SidecarProcess,
) -> None:
    project_id = _create_project(sidecar)
    started = time.monotonic()
    response = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "draft",
            "seed": 7,
            "config": {"runs": 80, "batchSize": 10},
        },
        request_id=910,
    )
    elapsed = time.monotonic() - started
    assert response["result"]["accepted"] is True
    assert elapsed < 0.1, f"réponse simulation.start trop lente: {elapsed:.3f}s"
    run_id = response["result"]["runId"]

    messages, terminal = _read_until(sidecar, _is_terminal)
    events = [message for message in messages if message["params"].get("runId") == run_id]
    assert terminal["method"] == "simulation.done"
    assert terminal["params"]["persisted"] is False
    assert terminal["params"]["result"]["runId"] == run_id

    partials = [event for event in events if event["method"] == "simulation.partial"]
    seqs = [event["params"]["seq"] for event in partials]
    assert seqs == sorted(seqs)
    assert seqs == list(range(1, len(seqs) + 1))
    assert events[-1]["method"] == "simulation.done"
    assert all(
        event["method"] != "simulation.partial"
        for event in events[events.index(terminal) + 1 :]
    )
    for event in partials:
        aggregates = event["params"]["aggregates"]
        assert "trajectories" not in aggregates
        assert aggregates["completedRuns"] <= aggregates["totalRuns"]

    data = sidecar.call("project.data", {"projectId": project_id}, request_id=911)
    assert data["result"]["run"] is None


def test_final_is_persisted_once_with_its_seed(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Final")
    response = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "final",
            "seed": 5,
            "config": {"runs": 60, "batchSize": 10},
        },
        request_id=920,
    )
    run_id = response["result"]["runId"]
    messages, terminal = _read_until(
        sidecar, lambda message: _is_terminal(message) and message["params"].get("runId") == run_id
    )
    assert messages[-1] is terminal
    assert terminal["method"] == "simulation.done"
    assert terminal["params"]["persisted"] is True
    assert terminal["params"]["result"]["seed"] == 5

    data = sidecar.call("project.data", {"projectId": project_id}, request_id=921)
    run = data["result"]["run"]
    assert run is not None
    assert run["id"] == run_id
    assert run["seed"] == 5
    assert run["runs"] == 60
    assert data["result"]["run"]["id"] == run_id

    # Le draft suivant ne doit pas créer une seconde ligne de run.
    sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "draft",
            "seed": 6,
            "config": {"runs": 30, "batchSize": 10},
        },
        request_id=922,
    )
    _read_until(sidecar, lambda message: _is_terminal(message))
    data = sidecar.call("project.data", {"projectId": project_id}, request_id=923)
    assert data["result"]["run"]["id"] == run_id


def test_final_carries_monthly_histograms_for_every_month(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Monthly")
    response = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "final",
            "seed": 11,
            "config": {"runs": 40, "batchSize": 10},
        },
        request_id=924,
    )
    run_id = response["result"]["runId"]
    _, terminal = _read_until(
        sidecar,
        lambda message: _is_terminal(message)
        and message["params"].get("runId") == run_id,
    )
    result = terminal["params"]["result"]
    months = result["monthly"]["values"]
    assert len(months) == 2
    for month in months:
        assert month["profitHistogram"], "histogramme de profit manquant"
        assert month["cashHistogram"], "histogramme de trésorerie manquant"
        assert sum(bin["count"] for bin in month["profitHistogram"]) == 40
    encoded = json.dumps(result["monthly"], separators=(",", ":")).encode("utf-8")
    assert len(encoded) < 200_000


def test_draft_partials_never_carry_monthly_histograms(
    sidecar: SidecarProcess,
) -> None:
    project_id = _create_project(sidecar, "Partial")
    response = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "draft",
            "seed": 12,
            "config": {"runs": 40, "batchSize": 10},
        },
        request_id=925,
    )
    run_id = response["result"]["runId"]
    messages, _ = _read_until(
        sidecar,
        lambda message: _is_terminal(message)
        and message["params"].get("runId") == run_id,
    )
    partials = [
        message
        for message in messages
        if message["method"] == "simulation.partial"
        and message["params"].get("runId") == run_id
    ]
    assert partials
    for partial in partials:
        for month in partial["params"]["aggregates"]["monthly"]["values"]:
            assert month.get("profitHistogram") is None
            assert month.get("cashHistogram") is None


def test_new_start_supersedes_the_previous_run(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Supersede")
    first = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "final",
            "seed": 1,
            "config": SLOW_CONFIG,
        },
        request_id=930,
    )
    first_id = first["result"]["runId"]
    notifications, second = sidecar.collect(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "final",
            "seed": 2,
            "config": SLOW_CONFIG,
        },
        request_id=931,
    )
    second_id = second["result"]["runId"]
    assert second["result"]["replacedRunId"] == first_id

    events = list(notifications)
    terminals: dict[str, dict[str, Any]] = {}
    deadline = time.monotonic() + 60
    while len(terminals) < 2:
        remaining = deadline - time.monotonic()
        assert remaining > 0
        message = sidecar.read_json(timeout=remaining)
        if message.get("method") is None:
            continue
        run_id = message["params"].get("runId")
        if run_id not in (first_id, second_id):
            continue
        events.append(message)
        if _is_terminal(message):
            terminals[run_id] = message

    assert terminals[first_id]["method"] == "simulation.cancelled"
    assert terminals[first_id]["params"]["reason"] == "simulation_superseded"
    assert terminals[second_id]["method"] == "simulation.done"

    first_partials = [
        event
        for event in events
        if event["method"] == "simulation.partial"
        and event["params"].get("runId") == first_id
    ]
    assert first_partials == [] or events.index(first_partials[-1]) < events.index(
        terminals[first_id]
    )
    second_partials = [
        event
        for event in events
        if event["method"] == "simulation.partial"
        and event["params"].get("runId") == second_id
    ]
    assert second_partials


def test_cancel_is_fast_and_stops_the_stream(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Cancel")
    response = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "final",
            "seed": 3,
            "config": SLOW_CONFIG,
        },
        request_id=940,
    )
    run_id = response["result"]["runId"]

    _read_until(
        sidecar,
        lambda message: message["method"] == "simulation.partial"
        and message["params"].get("runId") == run_id,
    )

    started = time.monotonic()
    _, cancelled = sidecar.collect(
        "simulation.cancel", {"runId": run_id}, request_id=941
    )
    assert cancelled["result"]["cancelled"] is True
    _, terminal = _read_until(
        sidecar,
        lambda message: message["method"] == "simulation.cancelled"
        and message["params"].get("runId") == run_id,
    )
    elapsed = time.monotonic() - started
    assert terminal["params"]["reason"] == "simulation_cancelled"
    assert elapsed < 0.15, f"annulation trop lente: {elapsed:.3f}s"

    late = _drain(sidecar)
    assert all(
        not (
            message.get("method") == "simulation.partial"
            and message["params"].get("runId") == run_id
        )
        for message in late
    )


def test_ping_answers_during_a_final(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Ping")
    response = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "final",
            "seed": 4,
            "config": SLOW_CONFIG,
        },
        request_id=950,
    )
    run_id = response["result"]["runId"]

    started = time.monotonic()
    _, ping = sidecar.collect("ping", {"echo": "during-final"}, request_id=951)
    elapsed = time.monotonic() - started
    assert ping["result"]["pong"] is True
    assert ping["result"]["echo"] == "during-final"
    assert elapsed < 0.5, f"ping bloqué pendant le calcul: {elapsed:.3f}s"

    sidecar.collect("simulation.cancel", {"runId": run_id}, request_id=952)
    _read_until(
        sidecar,
        lambda message: message["method"] == "simulation.cancelled"
        and message["params"].get("runId") == run_id,
    )


def test_simulation_rejects_invalid_params_and_unknown_runs(
    sidecar: SidecarProcess,
) -> None:
    project_id = _create_project(sidecar, "Erreurs")
    invalid = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "turbo",
            "seed": 1,
        },
        request_id=960,
    )
    assert invalid["error"]["code"] == -32006
    assert invalid["error"]["data"]["code"] == "simulation_invalid"

    missing_seed = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "draft",
        },
        request_id=961,
    )
    assert missing_seed["error"]["data"]["code"] == "simulation_invalid"

    unknown = sidecar.call(
        "simulation.cancel", {"runId": "inconnu"}, request_id=962
    )
    assert unknown["error"]["code"] == -32001
    assert unknown["error"]["data"]["code"] == "run_not_found"

    health = sidecar.call("health", request_id=963)
    assert isinstance(health["result"]["droppedMessages"], int)


def test_outbound_writer_drops_partials_but_never_terminal_messages() -> None:
    from sidecar import simulation_service

    class BlockingStream:
        def __init__(self) -> None:
            self.release = threading.Event()
            self.lines: list[bytes] = []
            self.lock = threading.Lock()

        def write(self, data: bytes) -> None:
            self.release.wait(timeout=5)
            with self.lock:
                self.lines.append(data)

        def flush(self) -> None:
            return None

    stream = BlockingStream()
    writer = simulation_service.OutboundWriter(stream, max_queue=2)
    writer.start()
    for seq in range(100):
        writer.send(
            {"jsonrpc": "2.0", "method": "simulation.partial", "params": {"seq": seq}},
            droppable=True,
        )
    sender = threading.Thread(
        target=lambda: writer.send(
            {"jsonrpc": "2.0", "method": "simulation.done", "params": {"seq": 6}},
            droppable=False,
        )
    )
    sender.start()
    time.sleep(0.05)
    stream.release.set()
    sender.join(timeout=2)
    writer.close(drain=True, timeout=2)

    payloads = [json.loads(line) for line in stream.lines]
    assert any(payload["method"] == "simulation.done" for payload in payloads)
    assert writer.dropped >= 1


def test_ten_rapid_starts_keep_one_active_run(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Charge")
    started_ids: list[str] = []
    replaced: list[str | None] = []
    events: list[dict[str, Any]] = []
    for index in range(10):
        notifications, response = sidecar.collect(
            "simulation.start",
            {
                "projectId": project_id,
                "scenario": SIMULATION_SCENARIO,
                "quality": "final",
                "seed": index,
                "config": SLOW_CONFIG,
            },
            request_id=970 + index,
        )
        events.extend(notifications)
        started_ids.append(response["result"]["runId"])
        replaced.append(response["result"].get("replacedRunId"))

    # Chaque nouveau start remplace un run antérieur, sans accumulation.
    assert replaced[0] is None
    assert all(
        previous in started_ids[:index]
        for index, previous in enumerate(replaced)
        if previous is not None
    )
    assert replaced[-1] is not None

    terminals: dict[str, dict[str, Any]] = {}

    def record(message: dict[str, Any]) -> None:
        run_id = message["params"].get("runId")
        if run_id not in started_ids or not _is_terminal(message):
            return
        assert run_id not in terminals, f"deux terminaux pour {run_id}"
        terminals[run_id] = message

    for message in events:
        record(message)

    deadline = time.monotonic() + 90
    while len(terminals) < len(started_ids):
        remaining = deadline - time.monotonic()
        assert remaining > 0, f"terminaux manquants: {terminals.keys()}"
        message = sidecar.read_json(timeout=remaining)
        if message.get("method") is None:
            continue
        record(message)

    for run_id in started_ids[:-1]:
        assert terminals[run_id]["method"] == "simulation.cancelled"
        assert terminals[run_id]["params"]["reason"] == "simulation_superseded"
    assert terminals[started_ids[-1]]["method"] == "simulation.done"

    _, data = sidecar.collect(
        "project.data", {"projectId": project_id}, request_id=999
    )
    assert data["result"]["run"]["id"] == started_ids[-1]


# ---------------------------------------------------------------------------
# Phase 11 — surface et recherche d'objectif
# ---------------------------------------------------------------------------

def _job_terminal(job_id: str, message: dict[str, Any]) -> bool:
    if message.get("method") not in {
        "simulation.done",
        "simulation.cancelled",
        "simulation.error",
    }:
        return False
    return message["params"].get("jobId") == job_id


def test_surface_job_returns_an_oriented_grid(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Surface")
    started = time.monotonic()
    response = sidecar.call(
        "simulation.surface",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "axisX": {"key": "unit_price", "minimum": 10, "maximum": 20},
            "axisY": {"key": "unit_cost", "minimum": 5, "maximum": 7},
            "metric": "profit_p50",
            "grid": [2, 2],
            "runs": 10,
            "seed": 9,
            "quality": "draft",
        },
        request_id=1300,
    )
    elapsed = time.monotonic() - started
    assert response["result"]["accepted"] is True
    assert elapsed < 0.5, f"réponse simulation.surface trop lente: {elapsed:.3f}s"
    job_id = response["result"]["jobId"]

    messages, terminal = _read_until(
        sidecar, lambda message: _job_terminal(job_id, message)
    )
    assert terminal["method"] == "simulation.done"
    result = terminal["params"]["result"]
    assert result["seed"] == 9
    assert result["grid"] == [2, 2]
    assert result["cost"] == 40
    assert result["xValues"] == [10.0, 20.0]
    assert result["yValues"] == [5.0, 7.0]
    assert result["zP50"][0][0] == pytest.approx(100.0)
    assert result["zP50"][0][1] == pytest.approx(300.0)
    assert result["zP50"][1][0] == pytest.approx(60.0)
    assert result["zP50"][1][1] == pytest.approx(260.0)

    partials = [
        message
        for message in messages
        if message["method"] == "simulation.surface.partial"
        and message["params"].get("jobId") == job_id
    ]
    assert [partial["params"]["rowIndex"] for partial in partials] == [0, 1]
    assert [partial["params"]["seq"] for partial in partials] == [1, 2]

    _, data = sidecar.collect(
        "project.data", {"projectId": project_id}, request_id=1301
    )
    assert data["result"]["run"] is None


def test_goal_seek_job_returns_a_feasible_decisions(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Objectif")
    response = sidecar.call(
        "simulation.goalseek",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "objective": {
                "metric": "profit_p50",
                "comparator": ">=",
                "target": 200,
            },
            "levers": [{"key": "unit_price", "minimum": 10, "maximum": 20}],
            "locked": [],
            "maxEvaluations": 20,
            "runs": 10,
            "seed": 4,
            "confirmQuality": None,
        },
        request_id=1310,
    )
    job_id = response["result"]["jobId"]
    _, terminal = _read_until(
        sidecar, lambda message: _job_terminal(job_id, message)
    )
    assert terminal["method"] == "simulation.done"
    result = terminal["params"]["result"]
    assert result["feasible"] is True
    assert result["achieved"] >= 200
    assert result["best"]["unit_price"] == pytest.approx(15)
    assert result["evaluations"] <= 20
    assert result["quality"] == "draft"
    assert result["trace"]


def test_goal_seek_reports_an_unreachable_target(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Infaisable")
    response = sidecar.call(
        "simulation.goalseek",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "objective": {
                "metric": "profit_p50",
                "comparator": ">=",
                "target": 10_000,
            },
            "levers": [{"key": "unit_price", "minimum": 10, "maximum": 20}],
            "maxEvaluations": 20,
            "runs": 10,
            "confirmQuality": None,
        },
        request_id=1320,
    )
    job_id = response["result"]["jobId"]
    _, terminal = _read_until(
        sidecar, lambda message: _job_terminal(job_id, message)
    )
    result = terminal["params"]["result"]
    assert result["feasible"] is False
    assert result["gap"] > 0
    assert "non atteignable" in result["message"]
    assert "Objectif atteint" not in result["message"]


def test_surface_cancel_by_job_id(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Annulation analyse")
    response = sidecar.call(
        "simulation.surface",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "axisX": {"key": "unit_price", "minimum": 10, "maximum": 20},
            "axisY": {"key": "unit_cost", "minimum": 5, "maximum": 7},
            "grid": [30, 30],
            "runs": 2_000,
            "seed": 3,
            "quality": "draft",
        },
        request_id=1330,
    )
    job_id = response["result"]["jobId"]
    notifications, cancelled = sidecar.collect(
        "simulation.cancel", {"jobId": job_id}, request_id=1331
    )
    assert cancelled["result"]["cancelled"] is True

    terminals = [
        message for message in notifications if _job_terminal(job_id, message)
    ]
    if terminals:
        terminal = terminals[0]
    else:
        _, terminal = _read_until(
            sidecar,
            lambda message: _job_terminal(job_id, message),
            timeout=15.0,
        )
    assert terminal["method"] == "simulation.cancelled"
    assert terminal["params"]["reason"] == "analysis_cancelled"


def test_surface_rejects_an_unknown_axis(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Axe inconnu")
    response = sidecar.call(
        "simulation.surface",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "axisX": {"key": "unknown", "minimum": 1, "maximum": 2},
            "axisY": {"key": "unit_cost", "minimum": 5, "maximum": 7},
            "grid": [2, 2],
            "runs": 5,
        },
        request_id=1340,
    )
    job_id = response["result"]["jobId"]
    _, terminal = _read_until(
        sidecar, lambda message: _job_terminal(job_id, message)
    )
    assert terminal["method"] == "simulation.error"
    assert terminal["params"]["code"] == "analysis_invalid"


# ---------------------------------------------------------------------------
# Phase 12 — trajectoires, provenance et explication
# ---------------------------------------------------------------------------


def test_provenance_trajectories_and_explain_flow(sidecar: SidecarProcess) -> None:
    project_id = _create_project(sidecar, "Provenance")
    started = sidecar.call(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": SIMULATION_SCENARIO,
            "quality": "draft",
            "seed": 4,
            "config": {"runs": 30, "batchSize": 10},
        },
        request_id=1400,
    )
    assert started["result"]["accepted"] is True
    run_id = started["result"]["runId"]

    _, terminal = _read_until(sidecar, _is_terminal)
    assert terminal["method"] == "simulation.done"
    assert terminal["params"]["runId"] == run_id

    provenance = sidecar.call(
        "simulation.provenance",
        {"runId": run_id, "metric": "profit_p50"},
        request_id=1401,
    )
    assert "error" not in provenance
    payload = provenance["result"]["provenance"]
    assert payload["runId"] == run_id
    assert payload["metric"] == "profit_p50"
    assert payload["seed"] == 4
    assert payload["runs"] == 30
    # Aucun nom de projet ni secret dans le payload transmis au modèle.
    assert project_id not in json.dumps(payload)

    trajectories = sidecar.call(
        "simulation.trajectories",
        {"runId": run_id, "count": 2},
        request_id=1402,
    )
    assert "error" not in trajectories
    served = trajectories["result"]
    assert served["runId"] == run_id
    assert served["runs"] == 30
    assert len(served["trajectories"]) == 2
    assert served["trajectories"][0]["index"] == 0
    assert len(served["trajectories"][0]["profitMonthly"]) == 2

    run_params = sidecar.call(
        "simulation.run_params",
        {"runId": run_id, "index": 0},
        request_id=1403,
    )
    assert "error" not in run_params
    drawn = run_params["result"]
    assert drawn["runId"] == run_id
    assert drawn["index"] == 0
    assert drawn["scenariosHash"]
    assert drawn["parameters"]

    explanation = sidecar.call(
        "simulation.explain",
        {"projectId": project_id, "runId": run_id, "metric": "profit_p50"},
        request_id=1404,
    )
    assert "error" not in explanation
    result = explanation["result"]
    assert result["source"] == "fallback"
    assert result["reason"] == "no_provider"
    assert result["cached"] is False
    assert result["explanation"]["summary"]


def test_branch_versions_and_comparison_workflow(sidecar: SidecarProcess) -> None:
    created = sidecar.call("project.create", {"name": "Branches RPC"}, request_id=1000)
    project_id = created["result"]["project"]["id"]
    saved = sidecar.call(
        "project.scenario.save",
        {
            "projectId": project_id,
            "name": "Base RPC",
            "scenario": SIMULATION_SCENARIO,
        },
        request_id=1001,
    )
    base_id = saved["result"]["scenario"]["id"]

    first = sidecar.call(
        "project.scenario.branch",
        {"projectId": project_id, "scenarioId": base_id, "label": "Variante A"},
        request_id=1002,
    )
    first_id = first["result"]["scenario"]["id"]
    second = sidecar.call(
        "project.scenario.branch",
        {"projectId": project_id, "scenarioId": base_id, "label": "Variante B"},
        request_id=1003,
    )
    second_id = second["result"]["scenario"]["id"]
    assert first["result"]["scenario"]["parentId"] == base_id
    assert first["result"]["scenario"]["branchLabel"] == "Variante A"

    listed = sidecar.call(
        "project.scenario.list", {"projectId": project_id}, request_id=1004
    )
    assert {item["scenarioId"] for item in listed["result"]["branches"]} == {
        base_id,
        first_id,
        second_id,
    }

    renamed = sidecar.call(
        "project.scenario.rename",
        {
            "projectId": project_id,
            "scenarioId": second_id,
            "name": "Variante B renommée",
            "branchLabel": "Variante B2",
        },
        request_id=1005,
    )
    assert renamed["result"]["scenario"]["branchLabel"] == "Variante B2"

    run_a = sidecar.call(
        "project.simulate",
        {
            "projectId": project_id,
            "scenarioId": first_id,
            "config": {"runs": 20, "seed": 7},
        },
        request_id=1006,
    )
    run_b = sidecar.call(
        "project.simulate",
        {
            "projectId": project_id,
            "scenarioId": second_id,
            "config": {"runs": 20, "seed": 7},
        },
        request_id=1007,
    )
    assert run_a["result"]["run"]["scenarioId"] == first_id
    assert run_b["result"]["run"]["scenarioId"] == second_id

    comparison = sidecar.call(
        "project.run.compare",
        {
            "projectId": project_id,
            "runIds": [run_a["result"]["run"]["id"], run_b["result"]["run"]["id"]],
        },
        request_id=1008,
    )
    assert comparison["result"]["sameSeed"] is True
    assert comparison["result"]["sameEngineVersion"] is True

    pinned = sidecar.call(
        "project.run.pin",
        {
            "projectId": project_id,
            "runId": run_a["result"]["run"]["id"],
            "pinned": True,
        },
        request_id=1009,
    )
    assert pinned["result"]["run"]["pinned"] is True

    refused = sidecar.call(
        "project.scenario.archive",
        {"projectId": project_id, "scenarioId": first_id},
        request_id=1010,
    )
    assert refused["error"]["code"] == -32602
    assert "confirmez" in refused["error"]["message"]

    archived = sidecar.call(
        "project.scenario.archive",
        {
            "projectId": project_id,
            "scenarioId": first_id,
            "confirmPinned": True,
        },
        request_id=1011,
    )
    assert archived["result"]["scenario"]["archivedAt"] is not None
    visible = sidecar.call(
        "project.scenario.list", {"projectId": project_id}, request_id=1012
    )
    assert first_id not in {item["scenarioId"] for item in visible["result"]["branches"]}

    restored_branch = sidecar.call(
        "project.scenario.unarchive",
        {"projectId": project_id, "scenarioId": first_id},
        request_id=1013,
    )
    assert restored_branch["result"]["scenario"]["archivedAt"] is None

    version = sidecar.call(
        "project.version.create",
        {"projectId": project_id, "scenarioId": first_id, "label": "Référence", "seed": 7},
        request_id=1014,
    )
    version_id = version["result"]["version"]["id"]
    versions = sidecar.call(
        "project.version.list", {"projectId": project_id}, request_id=1015
    )
    assert [item["id"] for item in versions["result"]["versions"]] == [version_id]

    restored = sidecar.call(
        "project.version.restore",
        {"projectId": project_id, "versionId": version_id},
        request_id=1016,
    )
    assert restored["result"]["scenario"]["id"] != first_id
    assert restored["result"]["scenario"]["parentId"] == first_id

    deleted = sidecar.call(
        "project.version.delete",
        {"projectId": project_id, "versionId": version_id},
        request_id=1017,
    )
    assert deleted["result"]["deleted"] is True
    remaining = sidecar.call(
        "project.version.list", {"projectId": project_id}, request_id=1018
    )
    assert remaining["result"]["versions"] == []


def test_template_list_and_import_are_wired(sidecar: SidecarProcess) -> None:
    listed = sidecar.call("template.list", {}, request_id=1100)
    templates = listed["result"]["templates"]
    assert "retail-depot-brazzaville" in {template["id"] for template in templates}
    assert listed["result"]["errors"] == []

    imported = sidecar.call(
        "project.createFromTemplate",
        {"templateId": "retail-depot-brazzaville"},
        request_id=1101,
    )
    created = imported["result"]
    assert created["project"]["metadata"]["templateId"] == "retail-depot-brazzaville"
    assert created["project"]["currency"] == "XAF"
    assert created["seed"] == 42
    assert [branch["branchLabel"] for branch in created["branches"]] == ["Prix -10 %"]
