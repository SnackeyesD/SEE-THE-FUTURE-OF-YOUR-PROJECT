# Packs de benchmarks

Référentiels locaux versionnés et signés (phase 08).

## Contenu

- `packs/` : packs JSON et signatures détachées `.sig`.
- `keys/public.json` : clés publiques Ed25519 autorisées. La clé privée reste hors du dépôt.
- `schema/benchmark-pack.schema.json` : schéma JSON généré depuis `see_benchmarks`.
- `tools/` : génération de clés, validation, signature et vérification.

## Commandes

```powershell
uv run --project packages/benchmarks python data/benchmark-packs/tools/export_schema.py
uv run --project packages/benchmarks python data/benchmark-packs/tools/build_pack.py data/benchmark-packs/packs/mon-pack.json --output data/benchmark-packs/packs/mon-pack.json
uv run --project packages/benchmarks python data/benchmark-packs/tools/sign_pack.py data/benchmark-packs/packs/mon-pack.json "$env:USERPROFILE\.seefuture\keys\benchmark-ed25519-2026.json"
uv run --project packages/benchmarks python data/benchmark-packs/tools/verify_pack.py data/benchmark-packs/packs/mon-pack.json
```

Chaque valeur porte un indicateur, une valeur, une unité, une devise, un pays, un secteur,
une source, une URL de source, une date, une fiabilité et des notes. Une valeur sans source
ni date est refusée. Les estimations doivent être marquées `estimate` et documentées.

Les packs sont chargés par le sidecar après vérification de signature, puis exposés via
`benchmark.lookup`, `benchmark.pack.list` et `benchmark.pack.import`.
