#!/usr/bin/env python3
"""Banc d'essai du sidecar (phase 01).

Lance le sidecar réel en JSON-RPC sur stdio et mesure :

- le temps de démarrage (première réponse ``health``) ;
- la latence ``ping`` au repos ;
- la latence ``simulate`` (draft 500 x 36, final 5 000 x 36) ;
- le **blocage** de la boucle mono-thread : un ``ping`` envoyé pendant un calcul
  long attend la fin du calcul (constat d'audit C3) ;
- la mémoire résidente du processus (RSS) avant/après calculs.

Ce script est volontairement autonome : il n'importe ni le moteur ni le
sidecar, il parle uniquement le protocole. Il doit être lancé avec le projet
``apps/desktop/src-tauri/sidecar`` pour que les dépendances Python soient
disponibles dans ``sys.executable``.

Usage :
    uv run --project apps/desktop/src-tauri/sidecar \
        python scripts/perf/bench_sidecar.py --json-out docs/perf/sidecar.json
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO = REPO_ROOT / "packages" / "engine" / "examples" / "retail_depot.json"


def _rss_mb(pid: int) -> float | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


class Sidecar:
    """Client JSON-RPC minimal, avec lecteur en arrière-plan."""

    def __init__(self, *, data_dir: Path) -> None:
        env = dict(os.environ)
        env["SEE_DATA_DIR"] = str(data_dir)
        env.setdefault("PYTHONUNBUFFERED", "1")
        self.started_at = time.perf_counter()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "sidecar"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=REPO_ROOT,
            text=True,
            bufsize=1,
        )
        self._next_id = 0
        self._responses: dict[int, dict[str, Any]] = {}
        self._responses_lock = threading.Lock()
        self._notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._stderr: list[str] = []
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _read_loop(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in payload and isinstance(payload.get("id"), int):
                with self._responses_lock:
                    self._responses[int(payload["id"])] = payload
            elif "method" in payload:
                self._notifications.put(payload)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr.append(line.rstrip())

    def send(self, method: str, params: dict[str, Any] | None = None) -> int:
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        return request_id

    def wait(self, request_id: int, *, timeout: float = 60.0) -> dict[str, Any]:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self._responses_lock:
                response = self._responses.pop(request_id, None)
            if response is not None:
                return response
            time.sleep(0.0005)
        raise TimeoutError(f"pas de réponse pour la requête {request_id} après {timeout}s")

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self.send(method, params)
        response = self.wait(request_id)
        if "error" in response:
            raise RuntimeError(f"{method}: {response['error']}")
        return response["result"]

    def close(self) -> None:
        with suppress(Exception):
            self.request("shutdown")
        try:
            if self.process.stdin is not None:
                self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()

    @property
    def pid(self) -> int:
        return self.process.pid

    def stderr_tail(self, limit: int = 20) -> list[str]:
        return self._stderr[-limit:]


def _load_scenario(horizon: int) -> dict[str, Any]:
    payload = json.loads(DEFAULT_SCENARIO.read_text(encoding="utf-8"))
    payload["horizonMonths"] = horizon
    return payload


def _latencies(fn, *, repeats: int) -> dict[str, Any]:
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000.0)
    return {
        "unit": "ms",
        "repeats": repeats,
        "samples": [round(value, 3) for value in samples],
        "median": round(statistics.median(samples), 3),
        "min": round(min(samples), 3),
        "max": round(max(samples), 3),
    }


def run(*, scenario_path: Path, repeats: int) -> dict[str, Any]:
    scenario_36 = _load_scenario(36)
    scenario_12 = _load_scenario(12)
    del scenario_path  # le protocole transporte le scénario, pas un chemin

    with tempfile.TemporaryDirectory(prefix="sf-bench-sidecar-") as tmp:
        sidecar = Sidecar(data_dir=Path(tmp))
        try:
            health = sidecar.request("health")
            startup_ms = (time.perf_counter() - sidecar.started_at) * 1000.0
            rss_start = _rss_mb(sidecar.pid)

            ping = _latencies(
                lambda: sidecar.request("ping", {"echo": "bench"}),
                repeats=repeats * 4,
            )

            draft_config = {"runs": 500, "seed": 42}
            final_config = {"runs": 5_000, "seed": 42}
            draft = _latencies(
                lambda: sidecar.request(
                    "simulate", {"scenario": scenario_36, "config": draft_config}
                ),
                repeats=repeats * 2,
            )
            final = _latencies(
                lambda: sidecar.request(
                    "simulate", {"scenario": scenario_36, "config": final_config}
                ),
                repeats=repeats,
            )

            # Constat C3 : la boucle est mono-thread. On envoie un calcul long
            # puis un ping immédiatement : le ping ne peut être servi qu'après.
            sidecar.send("simulate", {"scenario": scenario_36, "config": {"runs": 50_000, "seed": 42}})
            ping_started = time.perf_counter()
            ping_id = sidecar.send("ping", {"echo": "during-simulate"})
            sidecar.wait(ping_id, timeout=120)
            blocked_ms = (time.perf_counter() - ping_started) * 1000.0

            # Deuxième scénario pour vérifier que le sidecar reste fonctionnel.
            small = sidecar.request("simulate", {"scenario": scenario_12, "config": {"runs": 500, "seed": 7}})
            rss_after = _rss_mb(sidecar.pid)

            return {
                "sidecar": {
                    "protocolVersion": health.get("protocolVersion"),
                    "sidecarVersion": health.get("sidecarVersion"),
                    "python": health.get("python"),
                    "startupMs": round(startup_ms, 3),
                },
                "measurements": {
                    "pingAtRest": ping,
                    "draft500x36OverRpc": draft,
                    "final5000x36OverRpc": final,
                    "pingDuring50000x36": {
                        "unit": "ms",
                        "blockedMs": round(blocked_ms, 3),
                        "note": (
                            "La boucle rpc.py est mono-thread : le ping attend la fin du "
                            "calcul. Constat C3, correction en phase 06."
                        ),
                    },
                },
                "correctness": {
                    "smallRunOk": small.get("runs") == 500,
                    "smallRunDurationMs": small.get("durationMs"),
                },
                "memory": {
                    "rssBeforeMb": rss_start,
                    "rssAfterMb": rss_after,
                    "unit": "Mo (VmRSS du processus sidecar)",
                },
                "limitations": {
                    "cancellation": "non supportée (phase 04/06)",
                    "streaming": "aucun partiel, seulement simulate.progress (phase 04/06)",
                },
            }
        finally:
            sidecar.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    results = run(scenario_path=args.scenario.resolve(), repeats=max(1, args.repeats))
    text = json.dumps(results, ensure_ascii=False, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")

    measurements = results["measurements"]
    print(f"Sidecar {results['sidecar']['sidecarVersion']} (protocole {results['sidecar']['protocolVersion']})")
    print(f"démarrage            : {results['sidecar']['startupMs']} ms")
    print(f"ping au repos        : {measurements['pingAtRest']['median']} ms")
    print(f"draft 500x36 (RPC)   : {measurements['draft500x36OverRpc']['median']} ms")
    print(f"final 5000x36 (RPC)  : {measurements['final5000x36OverRpc']['median']} ms")
    print(f"ping pendant calcul  : {measurements['pingDuring50000x36']['blockedMs']} ms (blocage)")
    print(
        "mémoire RSS          : "
        f"{results['memory']['rssBeforeMb']} Mo → {results['memory']['rssAfterMb']} Mo"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
