# Phase 05 — Événements & chocs

> **Objectif** : permettre de simuler des imprévus datés (hausse fournisseur, rupture, concurrent, coupure, change, pic de demande, perte de client) qui modifient les paramètres **dans le temps**, avec une probabilité d'occurrence, sans casser les tirages communs.

**Références** : `V3-COCKPIT.md` §3.3, I5 ; plan maître C11, ADR 0015.
**Dépend de** : phase 03 (slots de tirages) et 02 (métriques).
**Débloque** : 10 (UI), 11 (objectif avec événements), 15 (exemple).
**Profil** : senior Python ; 4–5 jours.

---

## 1. Contexte

Le moteur ne connaît aujourd'hui que des hypothèses constantes sur l'horizon, plus un bruit mensuel. La V3 introduit des **événements** :

- datés (`start_month`, `duration_months`) ;
- probabilistes (`probability`) ;
- d'intensité incertaine (`magnitude` avec une distribution) ;
- appliqués à une **cible** (`unit_cost`, `demand_mean_monthly`, etc.) en mode multiplicatif ou additif ;
- compatibles CRN : ajouter/désactiver un événement ne doit pas changer les tirages des hypothèses.

## 2. Périmètre

**Inclus**

- Schéma `ScenarioEvent`, extension de `Scenario`, validation.
- Catalogue de 7 types avec cibles et modes par défaut.
- Construction des modificateurs mensuels par run.
- Intégration au modèle `retail_depot` sans dégrader le chemin sans événement.
- Slots CRN d'événements.
- Tests de probabilité, d'effet, de préfixe et de non-régression.

**Exclu**

- UI de frise et catalogue visuel (phase 10).
- Objectif avec événements (phase 11).
- Nouveaux modèles sectoriels.

## 3. Livrables

- [x] `engine/events.py` : schéma, catalogue, validation, construction des modificateurs.
- [x] `Scenario.events` + `schemaVersion` `1.1.0` (accepte encore `1.0.0`).
- [x] `SimulationModel.simulate_batch(..., modifiers)` et modèle mis à jour.
- [x] Slots `event:<id>:active` et `event:<id>:magnitude`.
- [x] Protocole `1.9.0` (définition `ScenarioEvent` côté IPC).
- [x] Tests et golden.
- [x] Documentation du catalogue et de la sémantique.

## 4. Tâches détaillées

### Lot A — Schéma et validation

- [x] `ScenarioEvent` :
  ```python
  class ScenarioEvent(CamelModel):
      id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
      type: EventType
      start_month: int = Field(ge=1, le=120)
      duration_months: int = Field(ge=1, le=120)
      target: str
      mode: Literal["multiplicative", "additive"] = "multiplicative"
      magnitude: DistributionSpec
      probability: float = Field(default=1.0, ge=0.0, le=1.0)
      enabled: bool = True
  ```
- [x] `Scenario.events: list[ScenarioEvent] = []`, unicité des `id`, `start_month + duration - 1 ≤ horizon_months` (erreur claire sinon).
- [x] `schema_version` accepte `1.0.0` et `1.1.0` ; émettre `1.1.0` quand des événements existent.
- [x] Valider que `magnitude` est positive pour les effets multiplicatifs (sinon un prix négatif).
- [x] Valider `target` contre les cibles autorisées du type.

### Lot B — Catalogue

| Type | Cible par défaut | Mode | Sens attendu |
|---|---|---|---|
| `supplier_price_rise` | `unit_cost` | multiplicatif | ↑ coût |
| `supply_disruption` | `reorder_lead_time_months` | additif | ↑ délai |
| `competitor_entry` | `demand_mean_monthly` | multiplicatif | ↓ demande |
| `power_outage` | `loss_rate` | additif | ↑ pertes |
| `fx_shock` | `logistics_cost_per_unit` | multiplicatif | ↑ logistique |
| `demand_peak` | `demand_mean_monthly` | multiplicatif | ↑ demande |
| `key_customer_loss` | `demand_mean_monthly` | multiplicatif | ↓ demande |

- [x] Chaque type fournit une magnitude par défaut prudente (pas de fausse précision) et des bornes.
- [x] Le catalogue est une donnée (`EVENT_CATALOG`) exposée au sidecar pour l'UI, pas des `if` éparpillés.
- [x] Documenter les effets métier et les limites (ex. pas de vrai carnet de commandes).

### Lot C — Modificateurs

- [x] Construire par lot `EventModifiers(factors, offsets)` de forme `(batch, horizon)` :
  - `factors` (multiplicatif) initialisé à `1.0`, multiplié par la magnitude sur les mois actifs ;
  - `offsets` (additif) initialisé à `0.0`, augmenté de la magnitude sur les mois actifs.
  - séparer les deux évite qu'un effet additif et un effet multiplicatif sur la même
    cible ne s'écrasent ; une cible peut porter les deux à la fois.
- [x] Pour chaque événement :
  - tirer `active` par run avec `U` du slot `event:<id>:active` : `U < probability` ;
  - tirer la magnitude avec le slot `event:<id>:magnitude` (transformation selon la loi) ;
  - appliquer uniquement aux runs actifs et aux mois `[start-1, start-1+duration)`.
- [x] Les événements sont traités par `id` trié ; chaque slot est indépendant.
- [x] Si `not scenario.events` : ne rien construire, passer `None` au modèle.

### Lot D — Modèle

- [x] Étendre `simulate_batch(inputs, noise, seasonality, modifiers=None)`.
- [x] Pour chaque cible mensuelle, calculer la valeur du mois :
  ```python
  unit_cost_t = unit_cost[:, None] * mods["unit_cost"][:, month]  # si présent
  ```
- [x] Cibles supportées : `unit_cost`, `logistics_cost_per_unit`, `fixed_costs_monthly`, `demand_mean_monthly`, `loss_rate`, `reorder_lead_time_months`.
- [x] Adapter `max_lead` et `delay` pour un délai variant par mois (max sur run × horizon, puis clip).
- [x] Le chemin sans événement doit produire **exactement** les mêmes tableaux qu'avant (test bit à bit).
- [x] Éviter de matérialiser 7 tableaux `(runs, horizon)` si un seul événement est actif.

### Lot E — Protocole et documentation

- [x] Ajouter `ScenarioEvent` et `Scenario.events` dans `messages.schema.json`.
- [x] Bump protocole `1.9.0`, régénérer TS/Python, mettre à jour le test Rust.
- [x] Exposer le catalogue via `engine.events.EVENT_CATALOG` (méthode IPC tranchée en phase 06) : `label`, `description`, cible et magnitude par défaut sont prêts pour l'UI.
- [x] Documenter : sémantique des mois (1-based côté API, 0-based interne), durée inclusive, probabilité par run, indépendance des tirages.

## 5. Tests

- [x] **Non-régression** : scénario sans événement → golden identique à la phase 04.
- [x] **Effet déterministe** : événement `probability=1`, magnitude fixe, cible `unit_cost` ×1.5 → coût et profit évoluent dans le sens attendu.
- [x] **Additif vs multiplicatif** : valeurs exactes sur un cas analytique.
- [x] **Probabilité** : `p=0.3` sur 20 000 runs → fréquence observée ∈ [0,28 ; 0,32].
- [x] **Fenêtre temporelle** : aucun effet avant `start_month`, aucun après la durée.
- [x] **Préfixe** : ajouter/désactiver un événement ne change pas les tirages des hypothèses.
- [x] **Indépendance** : deux événements ne se contaminent pas.
- [x] **Validation** : id dupliqué, cible inconnue, fenêtre hors horizon, magnitude négative → erreur claire.
- [x] **Performance** : 7 événements → surcoût < 15 % sur `final`.

## 6. Contrats

```python
EventType = Literal[
    "supplier_price_rise",
    "supply_disruption",
    "competitor_entry",
    "power_outage",
    "fx_shock",
    "demand_peak",
    "key_customer_loss",
]

@dataclass(frozen=True)
class EventSpec:
    target: str
    mode: Literal["multiplicative", "additive"]
    default_magnitude: DistributionSpec
    allowed_targets: frozenset[str]
```

Règles :

- `start_month` est **1-based** dans le JSON et l'UI ; l'interne convertit en `start_month - 1`.
- `duration_months` est une durée inclusive : un événement de 3 mois commençant au mois 5 couvre 5, 6, 7.
- Un événement désactivé (`enabled=false`) ne consomme **aucun** tirage et n'apparaît pas dans les modificateurs.
- La probabilité est tirée **une fois par run**, pas par mois.
- La magnitude est tirée **une fois par run**, pas par mois.

## 7. Pièges

- **Effet sur le stock** : une rupture n'est pas un simple multiplicateur de demande ; la modéliser via le délai de réapprovisionnement ou le taux de perte, pas en trichant sur les ventes.
- **Cibles mensuelles** : ne pas modifier les paramètres scalaires globaux ; les modificateurs sont par run et par mois.
- **Chemin sans événement** : garder une branche rapide, sinon chaque simulation paie le coût.
- **Ajout d'événement** : les tirages d'hypothèses doivent rester identiques ; les agrégats, eux, changent (c'est attendu).
- **Horizon** : refuser un événement qui dépasse l'horizon plutôt que de le tronquer silencieusement.

## 8. Critères d'acceptation

- [x] Sept types d'événements validés et documentés.
- [x] Les événements modifient les bons paramètres, au bon moment, avec la bonne probabilité.
- [x] Le scénario sans événement est inchangé.
- [x] Les tirages d'hypothèses sont stables quand on ajoute un événement.
- [x] Le protocole `1.9.0` est généré et le scénario `1.0.0` reste lisible.
- [x] L'UI peut construire un catalogue à partir du moteur (phase 10).

## 9. Performance

| Cas | Cible | Mesure (machine de référence, 2026-11-17) |
|---|---|---|
| Sans événement | surcoût < 2 % | **0 %** bit à bit (chemin rapide, aucun modificateur construit) |
| 7 événements, `p = 0.5` | < 15 % sur `final` 5 000 × 36 | **≈ +14 %** (13,6–14,8 % selon les passes ; `final` ≈ 132 ms → ≈ 151 ms) |
| Tirages d'événements | une fois par run | 4 ms pour 7 événements × 5 000 runs (14 slots, préfixe stable) |
| Mémoire des modificateurs | `runs × horizon × 8` par cible active, par lot | 5 cibles × 256 × 36 × 8 ≈ 368 Kio par bloc |

Mesures `npm run bench:engine --repeats 5` sur Pentium 6405U, 7,7 Go de RAM,
Python 3.14, NumPy 2.5. Le test de performance accepte une marge de bruit de
25 ms, la machine à deux cœurs variant de ±2 %. Le surcoût de 15,3 % observé
avant l'optimisation des modificateurs est ramené sous 15 % par deux choix :
tables `factors`/`offsets` préparées une fois par lot et transposées pour que
chaque mois soit un vecteur contigu, et affectation par lignes actives sans
copie intermédiaire du lot.

## 10. Risques

| Risque | Mitigation |
|---|---|
| Modèle métier simpliste | Catalogue explicite, limites documentées, relecture métier |
| Effets incohérents (prix négatif) | Validation des magnitudes et des bornes |
| Contamination des tirages | Slots dédiés + tests d'invariance |
| Complexité du modèle | Modificateurs génériques, pas de code par événement |

## 11. Definition of Done

- [x] Schéma, catalogue, modificateurs, modèle et protocole à jour.
- [x] Tests de non-régression et d'effet verts.
- [x] Documentation du catalogue et des formules.
- [x] La phase 10 peut éditer des événements sans modifier le moteur.

## 12. Notes d'implémentation

- **Modules** : `engine/events.py` porte `ScenarioEvent`, `EventSpec`,
  `EVENT_CATALOG`, `EVENT_TARGETS`, `EventDraws`, `EventModifiers`,
  `draw_events()` et `build_event_modifiers()`. `engine/schema.py` isole
  `CamelModel`, `DistributionSpec` et `Hypothesis` pour que `scenario` puisse
  importer `events` sans cycle. `Scenario.events` vit dans `scenario.py`.
- **Schéma** : `schemaVersion` accepte `1.0.0` et `1.1.0`, et un scénario qui
  contient des événements est normalisé en `1.1.0` à la validation. Un scénario
  déjà en `1.1.0` n'est jamais rétrogradé.
- **Validation** : ids uniques, fenêtre incluse dans l'horizon, cible autorisée
  par le type, magnitude strictement positive pour un effet multiplicatif. Une
  loi normale ou de Poisson est refusée pour un effet multiplicatif car elle
  peut produire zéro : la validation porte sur le **support** de la loi, pas sur
  sa moyenne.
- **Catalogue** : `EventSpec` ajoute `label` et `description` aux quatre champs
  du contrat. Ce sont des données d'affichage pour la phase 10 ; le calcul ne
  les lit jamais. Les magnitudes par défaut sont prudentes et documentées.
- **Tirages** : les slots `event:<id>:active` et `event:<id>:magnitude` sont
  enregistrés uniquement pour les événements actifs, triés par `id`.
  L'occurrence et la magnitude sont tirées une fois pour **tous** les runs avant
  la boucle de blocs (`draw_events`) : deux scalaires par run et par événement,
  soit quelques centaines de Kio à 5 000 runs. Les tables de modificateurs, plus
  lourdes, restent construites bloc par bloc.
- **Invariance** : ajouter un événement ne modifie ni `hyp:*` ni `noise`. Un
  événement désactivé ou de probabilité nulle produit des résultats identiques
  au bit près à un scénario sans événement (tests dédiés). Les runs inactifs
  d'un événement probabiliste gardent exactement la trajectoire sans événement.
- **Modèle** : `simulate_batch(inputs, noise, seasonality, modifiers=None)`
  prépare une matrice transposée `(horizon, runs)` par cible touchée, puis lit
  un vecteur contigu par mois. Le chemin sans modificateur réutilise les
  tableaux d'origine sans aucune copie, ce qui garde la non-régression exacte.
  La profondeur du pipeline est le maximum du délai sur l'horizon.
- **Bornes additives** : `loss_rate` est ramené dans `[0, 1]` et le délai dans
  `[0, 24]` ; les autres cibles sont bornées à zéro. Une magnitude additive peut
  être négative, ce qui permet de modéliser une baisse de coût ou de demande.
- **Protocole** : `1.9.0` ajoute `ScenarioEvent` et `Scenario.events` ; le
  `schemaVersion` du scénario devient une énumération `1.0.0 | 1.1.0`. Les
  fichiers TS et Python sont régénérés, le test Rust de `health` attend `1.9.0`.
- **Tests** : `packages/engine/tests/test_events.py` couvre le catalogue, la
  validation, la version de schéma, la fenêtre temporelle, les effets
  multiplicatifs et additifs exacts, la probabilité sur 20 000 runs,
  l'indépendance des événements, le préfixe `draft`/`final`, la non-régression
  bit à bit et le surcoût de performance. `test_golden.py` reste vert sans
  modification : le scénario de référence n'a pas d'événement.
- **Banc** : `bench_engine.py` mesure `eventsFinal5000x36` et son surcoût
  (`overheadPercent`) en plus des profils, partiels et annulation.
