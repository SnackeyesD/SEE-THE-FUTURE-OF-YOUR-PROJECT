from __future__ import annotations

import argparse
import json
from pathlib import Path

import jsonschema
from see_benchmarks.schema import BenchmarkPack


def main() -> int:
    parser = argparse.ArgumentParser(description="Valide et canonicalise un pack de benchmarks.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "benchmark-pack.schema.json",
    )
    args = parser.parse_args()

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)
    pack = BenchmarkPack.model_validate(payload)
    canonical = pack.model_dump(by_alias=True, mode="json")
    text = json.dumps(canonical, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
        print(f"{args.output} ({len(pack.values)} valeurs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
