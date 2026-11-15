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

### Calcul progressif et annulation

L'API reste rétrocompatible avec `simulate(scenario, config, progress=callback)`.
Les options progressives sont des arguments nommés :

```python
from engine import CancelToken, SimulationConfig, simulate

token = CancelToken()
result = simulate(
    scenario,
    SimulationConfig(seed=42),
    quality="final",                 # "draft" ou "final"
    on_progress=lambda fraction: ...,  # 0.0 → 1.0, strictement croissant
    on_partial=lambda partial: ...,    # PartialAggregates
    cancel=token,
)
print(result.quality, result.convergence)
```

`progress` est un alias historique de `on_progress` ; si les deux sont fournis,
les deux callbacks sont appelés. Le calcul est découpé en blocs et le jeton est
vérifié **entre deux blocs**. Une annulation lève `SimulationCancelled` (sous-classe
d'`EngineError`) après le bloc en cours, sans publier de partiel supplémentaire.

### Profils de qualité

| Qualité | Runs | Bloc | Convergence |
|---|---|---|---|
| `draft` | 500 | 256 | 1 transition stable, au moins 500 runs |
| `final` | 5 000 | 256 | 2 transitions stables, au moins 2 000 runs |

Pour les calculs beaucoup plus grands (CLI, bancs), le bloc du profil est élargi
jusqu'à 2 048 runs afin de garder au plus 64 blocs : le coût d'appel du modèle
dépend peu du nombre de runs, et 100 000 runs en blocs de 256 seraient inutilement
lents. Un `batchSize` explicite reste toujours respecté, même s'il est plus petit.

La précédence est stricte : un champ **explicitement fourni** dans
`SimulationConfig` gagne toujours sur le profil. Par exemple
`SimulationConfig(runs=10_000)` exécute 10 000 runs avec le bloc du profil (256)
si `batchSize` n'est pas fourni. Les valeurs par défaut de `SimulationConfig`
(10 000 runs, `batchSize` 50 000) restent inchangées pour les appelants qui
construisent l'objet sans le passer à `simulate`.

`draft` et `final` partagent les mêmes tirages : les 500 premiers runs du
`final` sont **identiques** au `draft` (test `test_draft_is_an_exact_prefix_of_final`).

### Partiels

`PartialAggregates` contient `completed_runs`, `total_runs`, les métriques
principales, l'histogramme du profit, les bandes mensuelles et l'état de
convergence. Il ne contient **jamais** de trajectoire, de paramètre par run ou
d'échantillon brut. `to_dict()` produit le payload camelCase prêt pour l'IPC.

- Les métriques probabilistes d'un partiel utilisent au plus 5 000 runs
  régulièrement espacés dans le préfixe ; les moyennes mensuelles restent
  exactes car elles viennent de l'état d'agrégation complet.
- Les bandes mensuelles d'un partiel utilisent au plus 1 000 runs, contre
  2 000 pour le résultat final.
- Les bornes de l'histogramme sont fixées au premier bloc, puis élargies
  **symétriquement** autour du même centre si une valeur sort de la plage. Elles
  ne rétrécissent jamais et ne changent pas sans extension justifiée.
- Les histogrammes mensuels sont omis des partiels. Pour 5 000 runs × 36 mois,
  le payload mesuré est d'environ 26 Kio (limite : 50 Kio).
- Le nombre de partiels est plafonné à 64 par calcul ; au-delà, ils sont espacés
  régulièrement. La vérification d'annulation reste faite à chaque bloc.

### Convergence

À chaque bloc, le moteur calcule le vecteur
`[p10_profit, p50_profit, p90_profit, P(point mort), p50(min_cash)]`. La variation
relative maximale par rapport au bloc précédent est comparée au seuil de 2 %
avec un dénominateur protégé (`max(abs(x), 1e-9)`).

`ConvergenceState` expose :

- `converged` : seuil tenu sur le nombre de transitions du profil **et**
  nombre de runs minimal atteint ;
- `stability` : valeur d'affichage 0–1, inverse normalisée de la variation du
  dernier bloc ;
- `max_relative_change` : variation relative maximale observée ;
- `stable_blocks` : nombre de transitions stables consécutives.

Un calcul d'un seul bloc ne peut jamais être marqué convergé. Un `final` peut ne
jamais converger : c'est un état honnête, pas un blocage. La convergence est une
stabilité observée, jamais une garantie de précision.

`SimulationResult` expose `quality` et `convergence` en champs optionnels du
protocole : les résultats stockés avant la phase 04 restent lisibles.

## Schéma d'entrée

- `Scenario` : `schemaVersion`, `name`, `model`, `currency`, `horizonMonths`,
  `assumptions`, `seasonality`, `notes`.
- `Hypothesis` : valeur nominale, distribution optionnelle, provenance, confiance,
  bornes `min`/`max`.
- `DistributionSpec` : `normal`, `lognormal`, `triangular`, `uniform`, `poisson`,
  `empirical`.
- `SimulationConfig` : `runs`, `seed`, `batchSize`, `histogramBins`,
  `monthlyHistogramBins`, `histogramMonth`.

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

### Métriques cockpit (V3)

Les définitions de référence sont dans l'ADR 0015. Toutes sont calculées par le moteur ;
l'UI ne recalcule aucun nombre.

Pour chaque run :

- `cash_monthly[t]` est la trésorerie **après** le mois `t` (le stock initial est déjà payé) ;
- `min_cash = min(cash_monthly)` ;
- `break_even_month` est le premier mois où le **profit net cumulé** est `≥ 0` ;
  la sentinelle interne `horizon + 1` signifie « non atteint sur l'horizon » ;
- `financing_need = max(0, -min_cash)`.

Agrégats exposés dans `Metrics` :

| Champ | Formule |
|---|---|
| `cash_negative_probability` | proportion de runs avec `min_cash < 0` |
| `mean_min_cash` | moyenne de `min_cash` |
| `min_cash_p10/p50/p90` | quantiles linéaires de `min_cash` (méthode numpy) |
| `financing_need_p50` | `max(0, -min_cash_p50)` |
| `financing_need_p90` | `max(0, -min_cash_p10)` |
| `break_even_probability` | proportion de runs avec `break_even_month ≤ horizon` |
| `median_break_even_month` | médiane des runs atteignant le point mort, `null` sinon |
| `min_cash_cdf` | CDF empirique `P(min_cash ≤ value)`, au plus 64 points triés |

`financing_need_p50/p90` sont des transformations monotones des quantiles de trésorerie :
elles évitent un second passage sur les runs et restent cohérentes avec l'éventail affiché.

Bandes et histogrammes mensuels :

- l'échantillon de runs est le **préfixe** `min(runs, 20 000)`, jamais un tirage aléatoire ;
  il est exposé par `runsRetained` et reste interne au moteur (non sérialisé) ;
- les bandes `profit_p10/p50/p90` et `cash_p10/p50/p90` sont calculées par mois sur un
  sous-échantillon régulier d'au plus 2 000 runs de ce préfixe ;
- `break_even_probability` mensuel est la proportion de runs dont le point mort est atteint
  au plus tard à ce mois (courbe de survie) ;
- les histogrammes mensuels de profit et de trésorerie ne sont produits que pour le mois
  `histogramMonth` (défaut `1`) ; `null` les désactive. Un mois supérieur à l'horizon lève
  `EngineError`. Les bornes sont arrondies à cinq chiffres significatifs et les probabilités
  à cinq décimales, sauf si cet arrondi rendrait une borne non strictement croissante.

## Tirages communs et reproductibilité

Depuis la phase 03, le moteur ne tire plus directement dans les distributions de numpy : il
consomme une **banque de tirages** (`engine/draws.py`), puis applique une transformation
déterministe. Deux tirages de base par slot :

- `U ~ U(0,1)` ;
- `Z ~ N(0,1)`.

### Slots et identifiants

| Slot | Contenu |
|---|---|
| `hyp:<clé>` | une valeur par run pour chaque hypothèse résolue |
| `noise` | un `Z` de forme `(runs, horizon)` |
| `event:<id>:active`, `event:<id>:magnitude` | réservés à la phase 05 |

L'identifiant d'un slot est `BLAKE2b(nom, digest_size=8)` interprété en entier 64 bits non
signé. Ajouter, renommer ou réordonner un slot ne décale donc jamais les tirages des autres.

### Blocs, flux et cache

- Un bloc est généré par :
  ```python
  rng = np.random.Generator(
      np.random.PCG64(np.random.SeedSequence([seed, slot_id, block_index, stream]))
  )
  ```
  avec `stream = 0` pour `U` et `stream = 1` pour `Z`. Les deux flux sont **indépendants** :
  demander seulement `Z` ne consomme pas d'uniformes, et réciproquement.
- Les flux sont générés **à la demande** : une loi normale ne demande que `Z`, une
  triangulaire que `U`. Le mapping est centralisé dans `distribution_streams()`.
- Taille de bloc : `1024` runs pour les slots vectoriels (bruit), `2048` pour les slots
  scalaires. Le bruit n'est jamais alloué en `(runs, horizon)` : il est produit bloc par
  bloc, puis concaténé au plus au niveau du lot courant.
- Le cache est un LRU de `16` blocs (les deux flux d'un même bloc partagent une entrée).
  Une éviction ne change jamais les valeurs, elle provoque seulement une régénération
  déterministe.

### Transformations

| Loi | Flux | Formule |
|---|---|---|
| `normal` | `Z` | `moyenne + écart_type × Z` |
| `lognormal` | `Z` | `exp(mu + sigma × Z)` |
| `uniform` | `U` | `low + U × (high - low)` |
| `triangular` | `U` | inversion fermée de la CDF, cas `low == mode` et `mode == high` inclus |
| `empirical` | `U` | `searchsorted` sur la CDF cumulée des poids |
| `poisson` (λ ≤ 50 000) | `U` | inversion exacte de la CDF `P(X ≤ k)` |
| `poisson` (λ > 50 000) | `Z` | approximation normale, signalée dans le résultat |

Pour Poisson, la table de CDF est calculée en espace logarithmique (stable pour les grands
λ) et mise en cache par λ. Au-delà de `POISSON_EXACT_MAX = 50 000`, le moteur utilise
`N(λ, √λ)` arrondie et expose `approximations: ["poisson_normal"]` dans
`SimulationResult`. Le champ est optionnel : les résultats stockés sans lui restent
lisibles (protocole `1.8.0`, pas de rupture).

Les bornes `min`/`max` de l'hypothèse et du modèle sont appliquées **après** la
transformation, comme avant.

### Garanties testées

- **Préfixe** : `take(slot, n)[:k] == take(slot, k)` pour tout `k ≤ n`, y compris aux
  frontières de blocs (`250`, `256`, `257`, `500`, `1000`, `1023`, `1024`, `1025`,
  `2047`, `2048`).
- **Paramètres** : changer `mean/std`, `low/mode/high`, etc. ne modifie ni `U` ni `Z`.
- **Famille** : passer de `normal` à `triangular` conserve les deux flux du slot ; seules
  les valeurs transformées changent.
- **Ordre et ajout** : réordonner les hypothèses ou en ajouter une ne décale aucun tirage
  existant.
- **Lots** : la taille de lot ne change pas les tirages, seulement le découpage des appels
  à la banque.
- **Cache** : vider le cache ne change aucune valeur.

Aucun appel à l'état aléatoire global de numpy n'est effectué. Même scénario, même graine
et même configuration ⇒ mêmes agrégats ; `runId` et `durationMs` restent des métadonnées
non reproductibles. L'échantillon de runs est un préfixe : augmenter `runs` conserve les
runs déjà échantillonnés.

## Performance et mémoire

Cible : **100 000 runs en moins de 2 s** sur la machine de référence (test de performance
dans `tests/test_performance.py`). Les hypothèses sont tirées bloc par bloc, le bruit
mensuel est généré par blocs, et la boucle mensuelle est vectorisée sur les runs. Mémoire
approximative pour 100 000 runs et 12 mois : quelques dizaines de Mo, sans allocation
`runs × horizon × nombre_de_slots`.

Mesures de la phase 04 sur la machine de référence (`npm run bench:engine`,
scénario 36 mois, processeur Pentium 6405U) :

| Mesure | Cible | Plafond | Valeur mesurée |
|---|---|---|---|
| `draft` 500 × 36 | 50 ms | 150 ms | 18–26 ms |
| `final` 5 000 × 36 | 400 ms | 1,5 s | 150–170 ms |
| Latence d'annulation (après 512 runs) | 60 ms | 100 ms | 0,17 ms (max 0,19 ms) |
| Calcul d'un partiel | 10 ms | 30 ms | 7–9 ms médian, ≤ 19 ms max |
| Payload d'un partiel | < 50 Kio | 500 Kio | 26,1 Kio |

Le découpage en blocs de 256 ajoute environ 2× de surcoût au calcul `final` par rapport à
la phase 03, mais reste largement sous la cible et rend l'annulation quasi instantanée.
Pour les calculs beaucoup plus grands, le bloc est élargi jusqu'à 2 048 runs (au plus 64
blocs) : 100 000 runs × 36 restent sous la cible de 2 s (≈ 0,9 s mesurée). Les métriques V3
ajoutent :

- un échantillon de préfixe plafonné à 20 000 runs : 20 000 × 36 × 3 tableaux `float64`
  ≈ 17 Mo, plus les paramètres tirés ;
- le calcul des bandes sur au plus 2 000 runs pour le résultat final et 1 000 pour un
  partiel ;
- un payload final d'environ 28–30 Kio pour 5 000 runs × 36 mois avec un mois
  d'histogramme sélectionné (limite : 100 Kio hors trajectoires).

## Limites assumées

- Modèle volontairement simple : pas de saisonnalité intra-mensuelle, pas de crédit, pas de
  coûts d'achat variables selon le volume, pas de multi-produits.
- Les distributions sont indépendantes entre hypothèses ; aucune corrélation explicite.
- Les paramètres par défaut sont prudents et doivent être revus par un expert métier.
- Le délai de réapprovisionnement est arrondi au mois entier, avec un minimum de 1.
- Les champs V3 sont optionnels dans le protocole : un résultat stocké avant la phase 02
  reste lisible, avec `null` pour les métriques indisponibles.
- Les golden tests sont sensibles aux changements de version de numpy ; ils doivent être
  rejoués à chaque montée de version.
