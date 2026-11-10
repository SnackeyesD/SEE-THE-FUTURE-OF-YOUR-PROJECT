from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from . import __version__, simulate
from .errors import EngineError
from .models import get_model
from .scenario import Scenario, SimulationConfig


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("doit être un entier strictement positif")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("doit être un entier positif ou nul")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m engine",
        description="Moteur de simulation déterministe de See The Future.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--scenario", required=True, type=Path)
        subparser.add_argument("--runs", type=_positive_int)
        subparser.add_argument("--seed", type=_non_negative_int)
        subparser.add_argument("--batch-size", type=_positive_int)
        subparser.add_argument("--histogram-bins", type=_positive_int)
        subparser.add_argument("--quiet", action="store_true")

    run_parser = subparsers.add_parser("run", help="exécute une simulation")
    add_common(run_parser)
    run_parser.add_argument("--output", type=Path)

    validate_parser = subparsers.add_parser("validate", help="valide un scénario")
    validate_parser.add_argument("--scenario", required=True, type=Path)

    benchmark_parser = subparsers.add_parser("benchmark", help="mesure la performance")
    add_common(benchmark_parser)
    benchmark_parser.add_argument("--output", type=Path)

    return parser


def _load_scenario(path: Path) -> Scenario:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Scenario.model_validate(payload)


def _build_config(args: argparse.Namespace) -> SimulationConfig:
    values: dict[str, Any] = {}
    if getattr(args, "runs", None) is not None:
        values["runs"] = args.runs
    if getattr(args, "seed", None) is not None:
        values["seed"] = args.seed
    if getattr(args, "batch_size", None) is not None:
        values["batch_size"] = args.batch_size
    if getattr(args, "histogram_bins", None) is not None:
        values["histogram_bins"] = args.histogram_bins
    return SimulationConfig(**values)


def _write_json(payload: dict[str, Any], path: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        sys.stdout.write(text)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _progress_printer(enabled: bool) -> Callable[[float], None] | None:
    if not enabled:
        return None

    def report(fraction: float) -> None:
        sys.stderr.write(f"\rSimulation {fraction * 100:6.2f}%")
        sys.stderr.flush()
        if fraction >= 1.0:
            sys.stderr.write("\n")

    return report


def _run(args: argparse.Namespace) -> int:
    scenario = _load_scenario(args.scenario)
    config = _build_config(args)
    result = simulate(
        scenario,
        config,
        progress=_progress_printer(not args.quiet),
    )
    _write_json(result.to_dict(), args.output)
    return 0


def _validate(args: argparse.Namespace) -> int:
    scenario = _load_scenario(args.scenario)
    model = get_model(scenario.model)
    resolved = model.resolve(scenario)
    payload = {
        "ok": True,
        "engineVersion": __version__,
        "model": scenario.model,
        "assumptions": {
            key: {
                "value": hypothesis.value,
                "simulated": hypothesis.distribution is not None,
            }
            for key, hypothesis in sorted(resolved.items())
        },
    }
    _write_json(payload, None)
    return 0


def _benchmark(args: argparse.Namespace) -> int:
    scenario = _load_scenario(args.scenario)
    config = _build_config(args)
    result = simulate(
        scenario,
        config,
        progress=_progress_printer(not args.quiet),
    )
    seconds = result.duration_ms / 1000.0
    summary = {
        "runs": result.runs,
        "seed": result.seed,
        "engineVersion": result.engine_version,
        "durationMs": result.duration_ms,
        "runsPerSecond": result.runs / seconds if seconds > 0 else None,
        "meanProfit": result.metrics.mean_profit,
        "p10": result.metrics.p10,
        "p50": result.metrics.p50,
        "p90": result.metrics.p90,
    }
    _write_json(summary, None)
    if args.output is not None:
        _write_json(result.to_dict(), args.output)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "validate":
            return _validate(args)
        if args.command == "benchmark":
            return _benchmark(args)
        parser.error(f"commande inconnue: {args.command}")
    except ValidationError as exc:
        sys.stderr.write("Scénario ou configuration invalide :\n")
        for error in exc.errors(include_url=False):
            location = ".".join(str(part) for part in error["loc"])
            sys.stderr.write(f"  - {location}: {error['msg']}\n")
        return 2
    except (EngineError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Erreur: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
