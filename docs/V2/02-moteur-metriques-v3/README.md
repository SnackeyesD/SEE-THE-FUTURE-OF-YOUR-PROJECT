# Phase 02 — Métriques cockpit

> **Objectif** : produire les chiffres que le cockpit doit afficher (point mort en mois, trésorerie négative, besoin de financement, bandes mensuelles) et les exposer dans le protocole, **avant** toute UI.

**Références** : `V3-COCKPIT.md` §3.6, §6.1, I2–I4 ; plan maître C1, C2.
**Dépend de** : phase 01 (définitions figées, ADR 0015).
**Débloque** : 03, 04, 07, 09, 12.
**Profil** : senior Python (moteur numérique) ; 4–5 jours.

---

## 1. Contexte

Le moteur actuel produit des agrégats utiles mais **pas ceux du cockpit** :

- `Metrics` contient profit, P10/P50/P90, probabilité de perte, revenus, coûts, stock, etc. ;
- `BreakEven` est un seuil théorique (`coûts fixes / marge unitaire`), pas le mois où l'entreprise devient rentable ;
- la trésorerie n'est exposée qu'en fin d'horizon (`mean_cash_end`), pas son minimum ni la probabilité qu'elle passe sous zéro ;
- `MonthlyAverages` ne contient que des **moyennes**, donc aucun éventail P10–P90 mensuel n'est traçable.

Sans cette phase, le cockpit ne peut afficher que des courbes moyennes : c'est incompatible avec le principe « toujours des fourchettes ».

## 2. Périmètre

**Inclus**

- Nouvelles métriques par run et agrégées.
- Bandes mensuelles P10/P50/P90 pour profit et trésorerie.
- Échantillon de runs déterministe conservé pour les trajectoires (phase 12).
- Extension du schéma protocole (`1.8.0`) et régénération TS/Python.
- Mise à jour assumée des golden tests.

**Exclu**

- CRN et blocs (phase 03).
- Événements (phase 05).
- Transport et notifications (phase 06).
- UI (phase 09).

## 3. Livrables

- [ ] `BatchResult` expose la trésorerie mensuelle et les valeurs par run nécessaires.
- [ ] `Metrics` contient : `cash_negative_probability`, `mean_min_cash`, `min_cash_p10/p50/p90`, `financing_need_p50/p90`, `break_even_probability`, `median_break_even_month`.
- [ ] Le résultat expose une **CDF du minimum de trésorerie** (≈ 64 points) pour que le seuil glissable du cockpit (phase 09) soit calculé par le moteur, pas par l'UI.
- [ ] `MonthlyAverage` contient les bandes `profit_p10/p50/p90`, `cash_p10/p50/p90` et `break_even_probability`.
- [ ] Le résultat final contient un **histogramme mensuel** (profit et trésorerie, 20–30 bins) pour le mois sélectionné dans le cockpit (phase 10) ; les partiels ne le contiennent pas.
- [ ] `SimulationResult` expose `runs_retained` et un échantillon interne non sérialisé.
- [ ] Schéma protocole `1.8.0`, types générés, `protocol:check` vert.
- [ ] Documentation des formules dans `packages/engine/README.md`.
- [ ] Tests unitaires, golden et de compatibilité.

## 4. Tâches détaillées

### Lot A — Collecte par run

- [ ] Dans `retail_depot.py`, stocker `cash_monthly` (shape `runs × horizon`) en plus de `cash_end`.
- [ ] Calculer par run : `min_cash`, `break_even_month` (premier mois où le profit net cumulé ≥ 0), `cash_negative_month` (premier mois < 0, optionnel).
- [ ] Ajouter ces champs à `BatchResult` ; ne pas casser les modèles existants.
- [ ] Vérifier que le cas sans événement reste **bit à bit identique** hors nouveaux champs.

### Lot B — Échantillon de runs

- [ ] Conserver les **premiers `min(runs, 20 000)` runs** (échantillon déterministe, compatible avec le préfixe de la phase 03).
- [ ] Stocker par run échantillonné : index, `profit_monthly`, `cash_monthly`, `revenue_monthly`, paramètres tirés (clé → valeur).
- [ ] Exposer un objet `RunSample` interne au moteur, **jamais sérialisé par défaut**.
- [ ] Documenter la mémoire : ~20 000 × 36 × 3 × 8 octets ≈ 17 Mo, plus paramètres ; plafond dur.
- [ ] Prévu pour la phase 12 : accès par index, tirage de ≤ 200 trajectoires.

### Lot C — Agrégats

- [ ] `build_metrics()` calcule les nouvelles métriques à partir de `profit`, `min_cash` et `break_even_month`.
- [ ] Définitions exactes (ADR 0015) :
  - point mort = premier mois avec profit net cumulé ≥ 0 ;
  - `break_even_probability` = proportion de runs avec point mort ≤ horizon ;
  - `median_break_even_month` = médiane des runs atteignant le point mort, `null` sinon ;
  - trésorerie négative = `min_cash < 0` ;
  - besoin de financement = `max(0, -min_cash)`.
- [ ] `build_monthly()` calcule les bandes à partir de l'échantillon, pas des sommes.
- [ ] Construire les histogrammes mensuels profit/trésorerie à partir de l'échantillon, avec des bornes fixes par mois (pas de saut entre deux calculs).
- [ ] Ajouter `break_even_probability` cumulée par mois (courbe de survie).
- [ ] Construire une CDF du minimum de trésorerie (quantiles échantillonnés, 64 points) : `P(min_cash ≤ x)`, pour le seuil glissable côté UI.
- [ ] Garantir P10 ≤ P50 ≤ P90 et probabilités dans `[0, 1]`.

### Lot D — Protocole

- [ ] Étendre `SimulationResult`, `Metrics`, `MonthlyAverage` dans `messages.schema.json`.
- [ ] Rendre les **nouveaux champs optionnels** côté schéma pour continuer à lire les runs stockés en v2.
- [ ] Bump `version` à `1.8.0` ; `npm run protocol:generate`.
- [ ] Mettre à jour le test Rust qui assert `protocolVersion == "1.7.0"`.
- [ ] Vérifier la taille du payload : un résultat final 36 mois doit rester < 100 Ko (hors trajectoires).

### Lot E — Tests et documentation

- [ ] Golden : régénérer `tests/golden/retail_depot_three_months.json` et justifier le diff.
- [ ] Test analytique : scénario à paramètres constants → point mort et trésorerie vérifiables à la main.
- [ ] Test de compatibilité : un ancien `result_json` (sans nouveaux champs) reste lisible par le sidecar et l'UI.
- [ ] Test de non-régression : les anciennes métriques gardent leurs valeurs.
- [ ] Documenter formules, unités, arrondis et cas limites (`null`).

## 5. Contrats et structures

```python
class Metrics(CamelModel):
    # champs existants conservés…
    cash_negative_probability: float
    mean_min_cash: float
    min_cash_p10: float
    min_cash_p50: float
    min_cash_p90: float
    financing_need_p50: float
    financing_need_p90: float
    break_even_probability: float
    median_break_even_month: int | None
    min_cash_cdf: list[CashCdfPoint] | None = None


class CashCdfPoint(CamelModel):
    value: float
    probability: float  # P(min_cash ≤ value)


class MonthlyAverage(CamelModel):
    # champs existants conservés…
    profit_p10: float | None = None
    profit_p50: float | None = None
    profit_p90: float | None = None
    cash_p10: float | None = None
    cash_p50: float | None = None
    cash_p90: float | None = None
    break_even_probability: float | None = None
    profit_histogram: list[HistogramBin] | None = None
    cash_histogram: list[HistogramBin] | None = None
```

```python
@dataclass(frozen=True)
class RunSample:
    indices: np.ndarray          # (n,)
    profit_monthly: np.ndarray   # (n, horizon)
    cash_monthly: np.ndarray     # (n, horizon)
    revenue_monthly: np.ndarray  # (n, horizon)
    parameters: dict[str, np.ndarray]  # clé -> (n,)
```

Règles :

- L'échantillon est **le préfixe** des runs, pas un tirage aléatoire : il reste stable quand `runs` augmente.
- Les bandes mensuelles portent sur cet échantillon ; le nombre de runs utilisé est affiché (`runsRetained`).
- Aucun champ « nombre » ne doit être calculé côté UI.

## 6. Pièges

- **Ne pas calculer les percentiles mensuels sur les sommes** : il faut les valeurs par run. C'est la raison d'être de `RunSample`.
- **Point mort** : préciser « profit net cumulé » et non « chiffre d'affaires » ou « trésorerie ». La trésorerie peut rester négative alors que le profit cumulé est positif (décalage de stock/impôt).
- **Runs non rentables** : ne pas les exclure de `break_even_probability` ; `median_break_even_month` est `null` si aucun run n'atteint le point mort.
- **Mémoire** : ne pas conserver l'échantillon si `runs` dépasse le plafond ; documenter la troncature.
- **Compatibilité** : un ancien run stocké ne doit pas faire planter l'UI ; champs optionnels + fallback « non disponible ».

## 7. Tests

| Test | Ce qu'il prouve |
|---|---|
| `test_metrics_v3.py::test_break_even_constant_case` | Formule du point mort |
| `test_metrics_v3.py::test_cash_negative_and_financing` | Trésorerie et besoin |
| `test_metrics_v3.py::test_percentile_order` | P10 ≤ P50 ≤ P90 partout |
| `test_metrics_v3.py::test_old_result_payload_still_valid` | Compatibilité protocole |
| `test_golden.py` | Non-régression assumée |
| `test_memory_sample_cap` | Plafond d'échantillon |

## 8. Critères d'acceptation

- [ ] Les KPI de la spec (point mort, financement, trésorerie) sont calculés par le moteur.
- [ ] Un graphique en éventail est possible avec les seules données du payload.
- [ ] Les anciens runs restent lisibles.
- [ ] Le payload final reste < 100 Ko et < 500 Ko avec les partiels.
- [ ] Les définitions sont écrites et relues par le produit.
- [ ] Aucune régression sur les métriques existantes.

## 9. Performance

- Surcoût de collecte < 10 % sur `final` 5 000 × 36.
- Mémoire de l'échantillon bornée à 20 000 runs (≈ 17 Mo de tableaux + paramètres).
- Le calcul des bandes mensuelles reste < 5 ms pour 5 000 runs.

## 10. Risques

| Risque | Mitigation |
|---|---|
| Définition métier contestée | ADR 0015 + relecture produit avant code |
| Mémoire excessive | Plafond 20 000, tableaux `float64` contigus |
| Rupture de compatibilité | Champs optionnels, test avec ancien payload |
| Diff golden massif | Justifier chaque écart, versionner le moteur |

## 11. Definition of Done

- [ ] Métriques et bandes disponibles dans `SimulationResult`.
- [ ] Protocole `1.8.0` généré et vérifié.
- [ ] Tests et golden verts, documentation des formules à jour.
- [ ] L'UI peut afficher P10/P50/P90 mensuels et les KPI sans calcul local.
