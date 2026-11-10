# `see-engine` — moteur de simulation

Moteur Monte Carlo déterministe de See The Future. Il produit **tous** les chiffres de
simulation ; le LLM ne calcule jamais à sa place. Le package ne dépend ni de l'UI, ni du
réseau, ni d'un fournisseur IA.

## Installation et commandes

```powershell
npm run engine:sync
npm run engine:test
npm run engine:lint

uv run --project packages/engine python -m engine validate --scenario packages/engine/examples/retail_depot.json
uv run --project packages/engine python -m engine run --scenario packages/engine/examples/retail_depot.json --runs 10000 --seed 42
uv run --project packages/engine python -m engine benchmark --scenario packages/engine/examples/retail_depot.json --runs 100000
```

`run` écrit le résultat JSON sur la sortie standard (ou dans `--output`). La progression va
sur `stderr`, ce qui garde `stdout` exploitable par un pipe.

## API Python

```python
from engine import Scenario, SimulationConfig, simulate

scenario = Scenario.model_validate_json(open("scenario.json", encoding="utf-8").read())
result = simulate(scenario, SimulationConfig(runs=10_000, seed=42))
print(result.metrics.p10, result.metrics.p50, result.metrics.p90)
```

`SimulationResult.to_dict()` sérialise en camelCase pour l'IPC.

## Schéma d'entrée

- `Scenario` : `schemaVersion`, `name`, `model`, `currency`, `horizonMonths`,
  `assumptions`, `seasonality`, `notes`.
- `Hypothesis` : valeur nominale, distribution optionnelle, provenance, confiance,
  bornes `min`/`max`.
- `DistributionSpec` : `normal`, `lognormal`, `triangular`, `uniform`, `poisson`,
  `empirical`.
- `SimulationConfig` : `runs`, `seed`, `batchSize`, `histogramBins`.

Les clés d'hypothèses sont en `snake_case` et ne peuvent contenir que des minuscules,
chiffres et `_`.

## Modèle `retail_depot`

### Hypothèses

| Clé | Unité | Défaut | Rôle |
|---|---|---|---|
| `initial_cash` | FCFA | requis | trésorerie de départ |
| `unit_price` | FCFA/unité | requis | prix de vente |
| `unit_cost` | FCFA/unité | requis | coût d'achat |
| `fixed_costs_monthly` | FCFA/mois | requis | coûts fixes |
| `demand_mean_monthly` | unités/mois | requis | demande moyenne |
| `demand_cv` | — | 0,2 | coefficient de variation mensuel |
| `loss_rate` | fraction | 0,02 | pertes mensuelles de stock |
| `logistics_cost_per_unit` | FCFA/unité | 0 | logistique variable |
| `target_stock_months` | mois | 1 | stock cible |
| `reorder_lead_time_months` | mois | 1 | délai de livraison (minimum effectif 1) |
| `initial_stock` | unités | 0 | stock de départ |
| `tax_rate` | fraction | 0 | impôt sur le bénéfice positif |

### Déroulé d'un mois

Pour chaque run et chaque mois `t` :

1. **Arrivées** : les commandes placées `délai` mois plus tôt entrent en stock.
2. **Pertes** : `perte = stock × loss_rate`, puis `stock disponible = stock - perte`.
3. **Demande** :
   `demande = demande_moyenne × saisonnalité[t] × exp(σ·z - σ²/2)`,
   avec `σ = sqrt(ln(1 + cv²))` et `z ~ N(0,1)`. La demande est tronquée à zéro.
4. **Ventes** : `vendues = min(demande, stock disponible)`.
5. **P&L** :
   - `revenu = vendues × prix`
   - `coût des ventes = vendues × coût`
   - `logistique = vendues × coût logistique`
   - `coût des pertes = perte × coût`
   - `résultat imposable = revenu - coût des ventes - logistique - coûts fixes - coût des pertes`
   - `impôt = max(résultat imposable, 0) × tax_rate`
   - `profit net = résultat imposable - impôt`
6. **Trésorerie** :
   `cash += revenu - arrivées × coût - logistique - coûts fixes - impôt`.
   Le stock initial est considéré comme déjà payé (coût irrécupérable) ; il n'apparaît donc
   pas en trésorerie mais reste valorisé dans le stock final.
7. **Réapprovisionnement** : si `stock final < demande moyenne × saisonnalité × stock cible`,
   la quantité manquante est commandée et arrive après le délai (au moins un mois).

### Agrégats

- Moyenne, médiane, écart-type (population), min/max, P10/P50/P90.
- Probabilité de perte et probabilité de profit positif.
- Histogramme du profit (bornes stables à graine et configuration fixées).
- Moyennes mensuelles : revenu, profit, demande, ventes, stock final, probabilité de rupture.
- Sensibilité : corrélation de Pearson entre chaque hypothèse échantillonnée et le profit ;
  la contribution est le carré de la corrélation normalisé à 1.
- Seuil de rentabilité : `coûts fixes moyens ÷ marge unitaire moyenne`, avec marge
  `prix - coût - logistique`.

## Reproductibilité

- Un seul générateur `numpy.random.Generator(PCG64(seed))` pour les hypothèses.
- Un second flux, dérivé de `SeedSequence([seed, 0x5EED])`, pour le bruit mensuel.
- Aucun appel à l'état aléatoire global de numpy.
- Les hypothèses sont échantillonnées dans l'ordre alphabétique de leurs clés.
- Même scénario, même graine et même configuration ⇒ mêmes agrégats. `runId` et
  `durationMs` sont des métadonnées non reproductibles.
- La taille des lots ne change pas les tirages ; seuls des écarts d'arrondi flottant
  négligeables peuvent apparaître dans les sommes mensuelles.

## Performance et mémoire

Cible : **100 000 runs en moins de 2 s** sur la machine de référence (test de performance
dans `tests/test_performance.py`). Les hypothèses et le bruit sont pré-générés ; la boucle
mensuelle est vectorisée sur les runs et découpée en lots. Mémoire approximative pour
100 000 runs et 12 mois : quelques dizaines de Mo.

## Limites assumées

- Modèle volontairement simple : pas de saisonnalité intra-mensuelle, pas de crédit, pas de
  coûts d'achat variables selon le volume, pas de multi-produits.
- Les distributions sont indépendantes entre hypothèses ; aucune corrélation explicite.
- Les paramètres par défaut sont prudents et doivent être revus par un expert métier.
- Le délai de réapprovisionnement est arrondi au mois entier, avec un minimum de 1.
- Les golden tests sont sensibles aux changements de version de numpy ; ils doivent être
  rejoués à chaque montée de version.
