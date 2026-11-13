from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
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

    def read_json(self, timeout: float = 5.0) -> dict[str, Any]:
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
    assert result["protocolVersion"] == "1.7.0"
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

