from __future__ import annotations

import json
from pathlib import Path

from see_benchmarks.schema import BenchmarkPack


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    destination = root / "schema" / "benchmark-pack.schema.json"
    schema = BenchmarkPack.model_json_schema(by_alias=True)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://seethefuture.local/benchmarks/benchmark-pack.schema.json",
        "title": "See The Future benchmark pack",
        "description": "Pack local de valeurs de référence sourcées et signées.",
        **schema,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
