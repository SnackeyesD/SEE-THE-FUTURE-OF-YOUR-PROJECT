"""Génère le catalogue d'événements TypeScript depuis le moteur.

Le catalogue est une **donnée** du moteur (:data:`engine.EVENT_CATALOG`).
L'UI ne doit ni le recopier à la main ni le demander au sidecar au runtime :
ce script produit ``packages/protocol/src/catalog.generated.ts`` et
``--check`` échoue si le fichier n'est plus synchronisé.

Usage :
    uv run --project packages/engine python packages/engine/scripts/export_events.py --write
    uv run --project packages/engine python packages/engine/scripts/export_events.py --check
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.events import EVENT_CATALOG, EVENT_TARGETS

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / "packages/protocol/src/catalog.generated.ts"

HEADER = """// AUTO-GENERATED FILE — DO NOT EDIT BY HAND.
// Source: packages/engine/engine/events.py (EVENT_CATALOG)
// Regenerate with: npm run catalog:generate
import type { DistributionSpec, ScenarioEvent } from "./generated";

export type EventType = ScenarioEvent["type"];

export type EventCatalogTarget = {
  id: string;
  label: string;
};

export type EventCatalogEntry = {
  type: EventType;
  label: string;
  description: string;
  target: string;
  targetLabel: string;
  mode: "multiplicative" | "additive";
  allowedTargets: EventCatalogTarget[];
  defaultMagnitude: DistributionSpec;
};
"""


def entries() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for event_type, spec in EVENT_CATALOG.items():
        result.append(
            {
                "type": event_type,
                "label": spec.label,
                "description": spec.description,
                "target": spec.target,
                "targetLabel": EVENT_TARGETS[spec.target].label,
                "mode": spec.mode,
                "allowedTargets": [
                    {"id": target, "label": EVENT_TARGETS[target].label}
                    for target in sorted(spec.allowed_targets)
                ],
                "defaultMagnitude": spec.default_magnitude.model_dump(
                    by_alias=True, exclude_none=True, mode="json"
                ),
            }
        )
    return result


def render() -> str:
    catalog = entries()
    body = ",\n".join(
        "  " + json.dumps(entry, ensure_ascii=False, indent=2).replace("\n", "\n  ")
        for entry in catalog
    )
    by_type = ",\n".join(
        f"  {json.dumps(entry['type'], ensure_ascii=False)}: "
        f"EVENT_CATALOG[{index}]"
        for index, entry in enumerate(catalog)
    )
    return (
        HEADER
        + "\n"
        + "export const EVENT_CATALOG: EventCatalogEntry[] = [\n"
        + body
        + ",\n];\n\n"
        + "export const EVENT_CATALOG_BY_TYPE: Record<EventType, EventCatalogEntry> = {\n"
        + by_type
        + ",\n};\n"
    )


def main(argv: list[str]) -> int:
    check = "--check" in argv
    content = render()
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None
    if check:
        if current != content:
            print(
                f"Out of date: {TARGET}. Run: npm run catalog:generate",
                file=sys.stderr,
            )
            return 1
        print("Event catalog is up to date.")
        return 0
    TARGET.write_text(content, encoding="utf-8")
    print(f"Generated {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
