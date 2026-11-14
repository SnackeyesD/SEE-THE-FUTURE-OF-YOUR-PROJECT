#!/usr/bin/env python3
"""Banc d'essai du moteur (phase 01).

Mesure la baseline réelle avant la V3 : profils draft/final, proxy de surface,
taille de payload, mémoire et quelques constats d'audit.

Usage :
    uv run --project packages/engine python packages/engine/bench/bench_engine.py \
        --json-out docs/perf/engine.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

import engine
from engine import Scenario, SimulationConfig, simulate

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENARIO = REPO_ROOT / "packages" / "engine" / "examples" / "retail_depot.json"


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "inconnu"


def _mem_total_mb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def _commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _machine() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": _cpu_model(),
        "cpuCount": os.cpu_count(),
        "memTotalMb": _mem_total_mb(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "engineVersion": engine.__version__,
        "commit": _commit(),
    }


def _measure(
    fn: Callable[[], Any],
    *,
    repeats: int,
    warmup: int = 1,
) -> dict[str, Any]:
    for _ in range(warmup):
        fn()
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


def _scenario_36_months(path: Path) -> Scenario:
    scenario = Scenario.model_validate_json(path.read_text(encoding="utf-8"))
    payload = scenario.model_dump(by_alias=True)
    payload["horizonMonths"] = 36
    return Scenario.model_validate(payload)


def _with_value(scenario: Scenario, key: str, value: float) -> Scenario:
    """Copie le scénario en rendant l'hypothèse déterministe (pas de distribution).

    Le moteur actuel ignore `value` quand une distribution est présente : c'est un
    constat d'audit, pas une façon de calculer une vraie surface.
    """
    copy = scenario.model_copy(deep=True)
    hypothesis = copy.assumptions[key]
    hypothesis.value = value
    hypothesis.distribution = None
    return copy


def _surface_proxy(scenario: Scenario, *, runs: int, grid: int, seed: int) -> dict[str, Any]:
    base_price = scenario.assumptions["unit_price"].value
    base_demand = scenario.assumptions["demand_mean_monthly"].value
    prices = np.linspace(base_price * 0.8, base_price * 1.2, grid)
    demands = np.linspace(base_demand * 0.8, base_demand * 1.2, grid)
    config = SimulationConfig(runs=runs, seed=seed)

    started = time.perf_counter()
    cells = 0
    checksum = 0.0
    for price in prices:
        pivot = _with_value(scenario, "unit_price", float(price))
        for demand in demands:
            point = _with_value(pivot, "demand_mean_monthly", float(demand))
            result = simulate(point, config)
            checksum += result.metrics.p50
            cells += 1
    elapsed = (time.perf_counter() - started) * 1000.0
    return {
        "grid": grid,
        "runsPerPoint": runs,
        "cells": cells,
        "totalRuns": cells * runs,
        "elapsedMs": round(elapsed, 3),
        "msPerCell": round(elapsed / cells, 3),
        "checksum": round(checksum, 3),
    }


def run(path: Path, *, repeats: int) -> dict[str, Any]:
    scenario = _scenario_36_months(path)
    seed = 42

    draft = _measure(
        lambda: simulate(scenario, SimulationConfig(runs=500, seed=seed)),
        repeats=repeats * 2,
    )
    final = _measure(
        lambda: simulate(scenario, SimulationConfig(runs=5_000, seed=seed)),
        repeats=repeats,
    )
    large = _measure(
        lambda: simulate(scenario, SimulationConfig(runs=20_000, seed=seed)),
        repeats=max(2, repeats // 2),
    )

    sample = simulate(scenario, SimulationConfig(runs=5_000, seed=seed))
    payload = sample.to_dict()
    payload_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())

    progress_calls = 0

    def _progress(_: float) -> None:
        nonlocal progress_calls
        progress_calls += 1

    progress_sample = simulate(
        scenario,
        SimulationConfig(runs=500, seed=seed),
        progress=_progress,
    )
    assert progress_sample.runs == 500

    # Constat d'audit : `value` est ignoré quand une distribution existe.
    baseline_price = scenario.assumptions["unit_price"].value
    shifted = scenario.model_copy(deep=True)
    shifted.assumptions["unit_price"].value = baseline_price * 1.01
    baseline_result = simulate(scenario, SimulationConfig(runs=2_000, seed=seed))
    shifted_result = simulate(shifted, SimulationConfig(runs=2_000, seed=seed))

    surface = _surface_proxy(scenario, runs=200, grid=15, seed=seed)

    return {
        "machine": _machine(),
        "scenario": {
            "path": str(path.relative_to(REPO_ROOT)),
            "horizonMonths": scenario.horizon_months,
            "assumptions": len(scenario.assumptions),
            "runs": 0,
        },
        "measurements": {
            "draft500x36": draft,
            "final5000x36": final,
            "large20000x36": large,
            "surfaceProxy15x15x200": surface,
        },
        "payload": {
            "final5000Bytes": payload_bytes,
            "final5000KiB": round(payload_bytes / 1024, 1),
        },
        "progress": {
            "runs": 500,
            "callbacks": progress_calls,
            "note": "baseline sans annulation ni partiels (phase 04)",
        },
        "cancellation": {"status": "not_supported", "note": "phase 04"},
        "memory": {
            "maxRssMb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            "unit": "Mo (maxRSS du processus de bench)",
        },
        "auditObservations": {
            "valueIgnoredWhenDistributionSet": {
                "meanProfitBaseline": round(baseline_result.metrics.mean_profit, 6),
                "meanProfitShiftedValue": round(shifted_result.metrics.mean_profit, 6),
                "identical": baseline_result.metrics == shifted_result.metrics,
                "explanation": (
                    "sample_hypothesis utilise `value` uniquement si distribution est None. "
                    "Changer value avec une distribution active ne change pas le tirage."
                ),
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    results = run(args.scenario.resolve(), repeats=max(2, args.repeats))
    text = json.dumps(results, ensure_ascii=False, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")

    measurements = results["measurements"]
    print(f"Machine : {results['machine']['cpu']} ({results['machine']['memTotalMb']} Mo)")
    print(f"draft 500x36      : {measurements['draft500x36']['median']} ms")
    print(f"final 5000x36     : {measurements['final5000x36']['median']} ms")
    print(f"large 20000x36    : {measurements['large20000x36']['median']} ms")
    print(
        "surface 15x15x200 : "
        f"{measurements['surfaceProxy15x15x200']['elapsedMs']} ms "
        f"({measurements['surfaceProxy15x15x200']['cells']} cellules)"
    )
    print(f"payload final     : {results['payload']['final5000KiB']} Kio")
    print(f"mémoire maxRSS    : {results['memory']['maxRssMb']} Mo")
    audit = results["auditObservations"]["valueIgnoredWhenDistributionSet"]
    print(
        "audit value/distribution : "
        + ("value ignoré" if audit["identical"] else "value pris en compte")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
