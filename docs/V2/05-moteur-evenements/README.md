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

- [ ] `engine/events.py` : schéma, catalogue, validation, construction des modificateurs.
- [ ] `Scenario.events` + `schemaVersion` `1.1.0` (accepte encore `1.0.0`).
- [ ] `SimulationModel.simulate_batch(..., modifiers)` et modèle mis à jour.
- [ ] Slots `event:<id>:active` et `event:<id>:magnitude`.
- [ ] Protocole `1.9.0` (définition `ScenarioEvent` côté IPC).
- [ ] Tests et golden.
- [ ] Documentation du catalogue et de la sémantique.

## 4. Tâches détaillées

### Lot A — Schéma et validation

- [ ] `ScenarioEvent` :
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
- [ ] `Scenario.events: list[ScenarioEvent] = []`, unicité des `id`, `start_month + duration - 1 ≤ horizon_months` (erreur claire sinon).
- [ ] `schema_version` accepte `1.0.0` et `1.1.0` ; émettre `1.1.0` quand des événements existent.
- [ ] Valider que `magnitude` est positive pour les effets multiplicatifs (sinon un prix négatif).
- [ ] Valider `target` contre les cibles autorisées du type.

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

- [ ] Chaque type fournit une magnitude par défaut prudente (pas de fausse précision) et des bornes.
- [ ] Le catalogue est une donnée (`EVENT_CATALOG`) exposée au sidecar pour l'UI, pas des `if` éparpillés.
- [ ] Documenter les effets métier et les limites (ex. pas de vrai carnet de commandes).

### Lot C — Modificateurs

- [ ] Construire par lot `modifiers: dict[str, np.ndarray]` de forme `(batch, horizon)` :
  - multiplicatif : initialisé à `1.0`, `multiplié` par la magnitude sur les mois actifs ;
  - additif : initialisé à `0.0`, `ajouté`.
- [ ] Pour chaque événement :
  - tirer `active` par run avec `U` du slot `event:<id>:active` : `U < probability` ;
  - tirer la magnitude avec le slot `event:<id>:magnitude` (transformation selon la loi) ;
  - appliquer uniquement aux runs actifs et aux mois `[start-1, start-1+duration)`.
- [ ] Les événements sont traités par `id` trié ; chaque slot est indépendant.
- [ ] Si `not scenario.events` : ne rien construire, passer `None` au modèle.

### Lot D — Modèle

- [ ] Étendre `simulate_batch(inputs, noise, seasonality, modifiers=None)`.
- [ ] Pour chaque cible mensuelle, calculer la valeur du mois :
  ```python
  unit_cost_t = unit_cost[:, None] * mods["unit_cost"][:, month]  # si présent
  ```
- [ ] Cibles supportées : `unit_cost`, `logistics_cost_per_unit`, `fixed_costs_monthly`, `demand_mean_monthly`, `loss_rate`, `reorder_lead_time_months`.
- [ ] Adapter `max_lead` et `delay` pour un délai variant par mois (max sur run × horizon, puis clip).
- [ ] Le chemin sans événement doit produire **exactement** les mêmes tableaux qu'avant (test bit à bit).
- [ ] Éviter de matérialiser 7 tableaux `(runs, horizon)` si un seul événement est actif.

### Lot E — Protocole et documentation

- [ ] Ajouter `ScenarioEvent` et `Scenario.events` dans `messages.schema.json`.
- [ ] Bump protocole `1.9.0`, régénérer TS/Python, mettre à jour le test Rust.
- [ ] Exposer le catalogue via une méthode ou une constante de protocole (décision en phase 06 ; en attendant, `engine.events.EVENT_CATALOG`).
- [ ] Documenter : sémantique des mois (1-based côté API, 0-based interne), durée inclusive, probabilité par run, indépendance des tirages.

## 5. Tests

- [ ] **Non-régression** : scénario sans événement → golden identique à la phase 04.
- [ ] **Effet déterministe** : événement `probability=1`, magnitude fixe, cible `unit_cost` ×1.5 → coût et profit évoluent dans le sens attendu.
- [ ] **Additif vs multiplicatif** : valeurs exactes sur un cas analytique.
- [ ] **Probabilité** : `p=0.3` sur 20 000 runs → fréquence observée ∈ [0,28 ; 0,32].
- [ ] **Fenêtre temporelle** : aucun effet avant `start_month`, aucun après la durée.
- [ ] **Préfixe** : ajouter/désactiver un événement ne change pas les tirages des hypothèses.
- [ ] **Indépendance** : deux événements ne se contaminent pas.
- [ ] **Validation** : id dupliqué, cible inconnue, fenêtre hors horizon, magnitude négative → erreur claire.
- [ ] **Performance** : 7 événements → surcoût < 15 % sur `final`.

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

- [ ] Sept types d'événements validés et documentés.
- [ ] Les événements modifient les bons paramètres, au bon moment, avec la bonne probabilité.
- [ ] Le scénario sans événement est inchangé.
- [ ] Les tirages d'hypothèses sont stables quand on ajoute un événement.
- [ ] Le protocole `1.9.0` est généré et le scénario `1.0.0` reste lisible.
- [ ] L'UI peut construire un catalogue à partir du moteur (phase 10).

## 9. Performance

- Sans événement : surcoût < 2 %.
- 7 événements : surcoût < 15 % sur `final` 5 000 × 36.
- Mémoire des modificateurs : `runs × horizon × 8` par cible active, calculée par lot.

## 10. Risques

| Risque | Mitigation |
|---|---|
| Modèle métier simpliste | Catalogue explicite, limites documentées, relecture métier |
| Effets incohérents (prix négatif) | Validation des magnitudes et des bornes |
| Contamination des tirages | Slots dédiés + tests d'invariance |
| Complexité du modèle | Modificateurs génériques, pas de code par événement |

## 11. Definition of Done

- [ ] Schéma, catalogue, modificateurs, modèle et protocole à jour.
- [ ] Tests de non-régression et d'effet verts.
- [ ] Documentation du catalogue et des formules.
- [ ] La phase 10 peut éditer des événements sans modifier le moteur.
