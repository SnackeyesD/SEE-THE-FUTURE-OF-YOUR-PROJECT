#!/usr/bin/env python3
"""Banc d'essai IPC de la phase 06 (flux, annulation, concurrence).

Mesure sur le sidecar réel :

- latence de réponse ``simulation.start`` (cible < 50 ms) ;
- ``ping`` pendant un ``final`` long (le transport ne doit plus bloquer) ;
- latence de bout en bout de ``simulation.cancel`` (cible < 150 ms) ;
- ordre et taille des partiels, présence de ``done`` ;
- un seul run actif quand deux ``start`` se succèdent ;
- mémoire RSS après une série de runs.

Usage :
    npm run bench:ipc
"""

from __future__ import annotations

import argparse
import json
import queue
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from bench_sidecar import REPO_ROOT, Sidecar, _load_scenario, _rss_mb

SLOW_CONFIG = {"runs": 120_000, "batchSize": 512}


def _collect_until(
    sidecar: Sidecar,
    predicate,
    *,
    timeout: float = 120.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    deadline = time.perf_counter() + timeout
    while True:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError("événement attendu non reçu")
        try:
            message = sidecar._notifications.get(timeout=remaining)  # noqa: SLF001
        except queue.Empty as exc:
            raise TimeoutError("événement attendu non reçu") from exc
        messages.append(message)
        if predicate(message):
            return messages, message


def _terminal(message: dict[str, Any]) -> bool:
    return message.get("method") in {
        "simulation.done",
        "simulation.cancelled",
        "simulation.error",
    }


def _start_latencies(
    sidecar: Sidecar, project_id: str, scenario: dict[str, Any], repeats: int
) -> dict[str, Any]:
    samples: list[float] = []
    for index in range(repeats):
        started = time.perf_counter()
        result = sidecar.request(
            "simulation.start",
            {
                "projectId": project_id,
                "scenario": scenario,
                "quality": "draft",
                "seed": index,
                "config": {"runs": 2_000, "batchSize": 512},
            },
        )
        samples.append((time.perf_counter() - started) * 1000.0)
        _collect_until(
            sidecar,
            lambda message, run_id=result["runId"]: _terminal(message)
            and message["params"].get("runId") == run_id,
        )
    return {
        "unit": "ms",
        "repeats": repeats,
        "samples": [round(value, 3) for value in samples],
        "median": round(statistics.median(samples), 3),
        "max": round(max(samples), 3),
    }


def _stream_shape(
    sidecar: Sidecar, project_id: str, scenario: dict[str, Any]
) -> dict[str, Any]:
    result = sidecar.request(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": scenario,
            "quality": "draft",
            "seed": 99,
            "config": {"runs": 8_000, "batchSize": 256},
        },
    )
    run_id = result["runId"]
    messages, terminal = _collect_until(
        sidecar, lambda message: _terminal(message) and message["params"].get("runId") == run_id
    )
    partials = [message for message in messages if message["method"] == "simulation.partial"]
    seqs = [message["params"]["seq"] for message in partials]
    sizes = [
        len(json.dumps(message["params"], ensure_ascii=False).encode("utf-8"))
        for message in partials
    ]
    done_index = messages.index(terminal)
    return {
        "terminal": terminal["method"],
        "partials": len(partials),
        "seqStrictlyIncreasing": seqs == sorted(seqs) and len(seqs) == len(set(seqs)),
        "maxPartialBytes": max(sizes) if sizes else 0,
        "partialAfterTerminal": sum(
            1
            for message in messages[done_index + 1 :]
            if message["method"] == "simulation.partial"
        ),
        "doneSeq": terminal["params"].get("seq"),
        "lastPartialSeq": seqs[-1] if seqs else None,
    }


def _cancel_latency(
    sidecar: Sidecar, project_id: str, scenario: dict[str, Any]
) -> dict[str, Any]:
    result = sidecar.request(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": scenario,
            "quality": "final",
            "seed": 3,
            "config": SLOW_CONFIG,
        },
    )
    run_id = result["runId"]
    _collect_until(
        sidecar,
        lambda message: message["method"] == "simulation.partial"
        and message["params"].get("runId") == run_id,
    )
    started = time.perf_counter()
    sidecar.request("simulation.cancel", {"runId": run_id})
    _, terminal = _collect_until(
        sidecar,
        lambda message: message["method"] == "simulation.cancelled"
        and message["params"].get("runId") == run_id,
    )
    return {
        "unit": "ms",
        "endToEnd": round((time.perf_counter() - started) * 1000.0, 3),
        "reason": terminal["params"]["reason"],
    }


def _ping_during_final(
    sidecar: Sidecar, project_id: str, scenario: dict[str, Any]
) -> dict[str, Any]:
    result = sidecar.request(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": scenario,
            "quality": "final",
            "seed": 4,
            "config": SLOW_CONFIG,
        },
    )
    run_id = result["runId"]
    started = time.perf_counter()
    sidecar.request("ping", {"echo": "during-final"})
    elapsed = (time.perf_counter() - started) * 1000.0
    sidecar.request("simulation.cancel", {"runId": run_id})
    _collect_until(
        sidecar,
        lambda message: message["method"] == "simulation.cancelled"
        and message["params"].get("runId") == run_id,
    )
    return {"unit": "ms", "pingDuringFinal": round(elapsed, 3)}


def _supersede(
    sidecar: Sidecar, project_id: str, scenario: dict[str, Any]
) -> dict[str, Any]:
    first = sidecar.request(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": scenario,
            "quality": "final",
            "seed": 5,
            "config": SLOW_CONFIG,
        },
    )
    second = sidecar.request(
        "simulation.start",
        {
            "projectId": project_id,
            "scenario": scenario,
            "quality": "final",
            "seed": 6,
            "config": SLOW_CONFIG,
        },
    )
    terminals: dict[str, str] = {}
    while len(terminals) < 2:
        message = sidecar._notifications.get(timeout=120)  # noqa: SLF001
        run_id = (message.get("params") or {}).get("runId")
        if run_id in (first["runId"], second["runId"]) and _terminal(message):
            terminals[run_id] = message["method"]
    return {
        "replacedRunId": second.get("replacedRunId"),
        "firstTerminal": terminals[first["runId"]],
        "secondTerminal": terminals[second["runId"]],
    }


def run() -> dict[str, Any]:
    scenario = _load_scenario(12)
    with tempfile.TemporaryDirectory(prefix="sf-bench-ipc-") as tmp:
        sidecar = Sidecar(data_dir=Path(tmp))
        try:
            health = sidecar.request("health")
            project = sidecar.request("project.create", {"name": "Bench IPC"})
            project_id = project["project"]["id"]
            rss_before = _rss_mb(sidecar.pid)

            start = _start_latencies(sidecar, project_id, scenario, repeats=10)
            stream = _stream_shape(sidecar, project_id, scenario)
            ping = _ping_during_final(sidecar, project_id, scenario)
            cancel = _cancel_latency(sidecar, project_id, scenario)
            supersede = _supersede(sidecar, project_id, scenario)
            rss_after = _rss_mb(sidecar.pid)

            return {
                "sidecar": {
                    "protocolVersion": health.get("protocolVersion"),
                    "sidecarVersion": health.get("sidecarVersion"),
                    "python": health.get("python"),
                },
                "measurements": {
                    "simulationStart": start,
                    "pingDuringFinal": ping,
                    "cancel": cancel,
                    "stream": stream,
                    "supersede": supersede,
                },
                "memory": {
                    "rssBeforeMb": rss_before,
                    "rssAfterMb": rss_after,
                    "unit": "Mo (VmRSS du processus sidecar)",
                },
                "environment": {
                    "machine": "Linux x86_64 (machine de développement)",
                    "note": "mesures ponctuelles, non comparables à un CI chargé",
                },
            }
        finally:
            sidecar.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out", type=Path, default=REPO_ROOT / "docs/perf/ipc.json"
    )
    args = parser.parse_args()
    results = run()
    text = json.dumps(results, ensure_ascii=False, indent=2)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(text + "\n", encoding="utf-8")

    measurements = results["measurements"]
    print(f"protocole {results['sidecar']['protocolVersion']}")
    print(f"start (médiane)        : {measurements['simulationStart']['median']} ms")
    print(f"start (max)            : {measurements['simulationStart']['max']} ms")
    print(f"ping pendant final     : {measurements['pingDuringFinal']['pingDuringFinal']} ms")
    print(f"cancel bout en bout    : {measurements['cancel']['endToEnd']} ms")
    print(f"partiels               : {measurements['stream']['partials']}")
    print(f"partiel max            : {measurements['stream']['maxPartialBytes']} octets")
    print(f"supersede              : {measurements['supersede']}")
    print(
        "mémoire RSS            : "
        f"{results['memory']['rssBeforeMb']} Mo → {results['memory']['rssAfterMb']} Mo"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
