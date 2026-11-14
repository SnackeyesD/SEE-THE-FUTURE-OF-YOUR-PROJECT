# ADR 0015 — Métriques cockpit et sémantique des événements

- **Statut** : accepté
- **Date** : 2026-11-14
- **Contexte** : phase 01, s'applique en phases 02 et 05

## Décision

### 1. Définitions métier

Toutes les valeurs sont calculées **par run**, puis agrégées. Les montants sont dans la devise du scénario.

| Métrique | Définition exacte | Cas limite |
|---|---|---|
| Profit net mensuel | `revenus − coût des ventes − logistique − coûts fixes − coût des pertes − impôt` (l'impôt est calculé sur le taxable positif). Implémentation actuelle : `retail_depot.py:187-193`. | Peut être négatif. |
| Profit net cumulé | Somme des profits nets mensuels du run, du mois 1 au mois `m`. | — |
| Point mort (mois) | Premier mois `m` où le **profit net cumulé** ≥ 0. | `null` si non atteint sur l'horizon. |
| P(point mort ≤ N) | Proportion de runs dont le point mort est non nul et ≤ N. | `N` ∈ {6, 12, 18, horizon}. |
| Médiane du point mort | Médiane des runs ayant atteint le point mort. | `null` si aucun run ne l'atteint. |
| Trésorerie mensuelle | Solde de trésorerie **en fin de mois** (`cash` après flux du mois). La trésorerie initiale n'est pas un mois. | Peut être négative. |
| Minimum de trésorerie | `min(cash_monthly[1..H])` par run. | — |
| Trésorerie négative | Run dont `min_cash < 0`. | Probabilité = proportion de runs. |
| Besoin de financement | `max(0, −min_cash)` par run ; exposé en P50 et P90. | 0 si jamais négative. |
| CDF du minimum de trésorerie | 64 points `(valeur, P(min_cash ≤ valeur))`, interpolables linéairement. | `null` pour un ancien run. |
| Bandes mensuelles | P10/P50/P90 de `profit_monthly` et `cash_monthly` **par mois**, calculés sur l'échantillon de runs. | — |
| Histogrammes mensuels | Distribution de `profit` et `cash` pour chaque mois, 20–30 bins, **résultat final uniquement**. | Absents des partiels. |

Règles :

- P10 ≤ P50 ≤ P90, probabilités dans `[0, 1]` (test bloquant).
- Aucun champ « nombre » n'est calculé dans l'UI : l'UI formate.
- Les valeurs sont stockées en pleine précision ; l'arrondi est un choix d'affichage.
- `mean_cash_end` existant reste disponible pour compatibilité, mais n'est plus le KPI de trésorerie.

### 2. Échantillon de runs

- Le moteur conserve les **premiers `min(runs, 20 000)` runs** (préfixe déterministe), avec index, `profit_monthly`, `cash_monthly`, `revenue_monthly` et paramètres tirés.
- Les bandes et histogrammes mensuels sont calculés sur cet échantillon ; `runsRetained` est exposé.
- L'échantillon n'est **jamais sérialisé par défaut** ; il est accessible sur demande (phase 12) et borné.
- Mémoire estimée : 20 000 × 36 × 3 × 8 octets ≈ 17 Mo, plus les paramètres.
- Si `runs > 20 000`, l'échantillon est tronqué et la troncature est documentée dans le résultat.

### 3. Événements

Objet `ScenarioEvent` :

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

Sémantique :

- `start_month` est **1-based** dans le JSON, l'API et l'UI ; l'interne convertit en `start_month - 1`.
- `duration_months` est **inclusive** : un événement de 3 mois commençant au mois 5 couvre 5, 6, 7.
- `start_month + duration_months - 1 ≤ horizon_months`, sinon erreur claire (pas de troncature silencieuse).
- `probability` est tirée **une fois par run**, pas par mois.
- `magnitude` est tirée **une fois par run**, pas par mois.
- `enabled=false` ne consomme **aucun** tirage et n'apparaît pas dans les modificateurs.
- Les ids sont uniques dans un scénario.
- Les tirages d'événements utilisent des slots dédiés (`event:<id>:active`, `event:<id>:magnitude`) : ajouter un événement ne change pas les tirages des hypothèses (ADR 0010).
- `schemaVersion` passe à `1.1.0` quand des événements existent ; `1.0.0` reste lisible.

Catalogue :

| Type | Cible par défaut | Mode | Sens attendu |
|---|---|---|---|
| `supplier_price_rise` | `unit_cost` | multiplicatif | ↑ coût |
| `supply_disruption` | `reorder_lead_time_months` | additif | ↑ délai |
| `competitor_entry` | `demand_mean_monthly` | multiplicatif | ↓ demande |
| `power_outage` | `loss_rate` | additif | ↑ pertes |
| `fx_shock` | `logistics_cost_per_unit` | multiplicatif | ↑ logistique |
| `demand_peak` | `demand_mean_monthly` | multiplicatif | ↑ demande |
| `key_customer_loss` | `demand_mean_monthly` | multiplicatif | ↓ demande |

Règles de validation :

- Une magnitude **multiplicative** doit être strictement positive (sinon prix ou demande négatifs).
- Une magnitude **additive** peut être signée, mais la valeur résultante est bornée par les `InputSpec` du modèle.
- La cible doit appartenir à la liste autorisée du type.
- Les magnitudes par défaut sont prudentes et documentées, pas des « pires cas » spectaculaires.
- Une rupture n'est pas modélisée comme une baisse de ventes arbitraire : elle agit sur le délai de réapprovisionnement ou le taux de perte.

## Contexte et raisons

- Le moteur actuel produit des KPI utiles mais pas ceux du cockpit : `Metrics` s'arrête au profit et à la trésorerie de fin d'horizon (`scenario.py:157-189`), `BreakEven` est un seuil théorique (`aggregation.py:130-152`), et `MonthlyAverages` ne contient que des moyennes (`aggregation.py:108-128`).
- Sans bandes mensuelles, le cockpit ne peut afficher qu'une ligne moyenne, ce qui contredit le principe « toujours des fourchettes ».
- Les événements sont la fonctionnalité « et si ? » centrale ; ils doivent être datés, probabilistes et compatibles avec les tirages communs.

## Alternatives

- **Point mort basé sur la trésorerie** : non retenu ; la trésorerie dépend du décalage de stock et des impôts, et rendrait le KPI incompréhensible.
- **Point mort basé sur le chiffre d'affaires** : non retenu ; ce n'est pas une rentabilité.
- **Modifier directement les paramètres scalaires globaux** : interdit ; les événements doivent varier par run et par mois.
- **Tirer la magnitude chaque mois** : créerait une variabilité non désirée et casserait le CRN.
- **Histogrammes dans les partiels** : trop lourds (≈ 60 Ko par mois × 36) ; réservés au final.

## Conséquences

- Le protocole passe à `1.8.0` (phase 02) puis `1.9.0` (phase 05) ; les types sont régénérés.
- Les golden tests changent de façon assumée ; le versionnement du moteur suit.
- Les anciens runs restent lisibles : les nouveaux champs sont optionnels côté schéma.
- L'UI affiche « non atteint » ou « non disponible », jamais `0` par défaut.
- La CDF permet un seuil glissable sans recalcul (phase 09) ; l'interpolation linéaire est autorisée, pas l'extrapolation.
- La phase 10 peut éditer des événements sans modifier le moteur ; le catalogue est exposé comme donnée.

## Vérification

- Cas analytique à paramètres constants : point mort et trésorerie vérifiables à la main.
- Test de probabilité d'événement : `p=0.3` sur 20 000 runs → fréquence ∈ [0,28 ; 0,32].
- Test de fenêtre : aucun effet avant `start_month`, aucun après la durée.
- Test de préfixe : ajouter/désactiver un événement ne change pas les tirages d'hypothèses.
- Test de non-régression : scénario sans événement → tableaux identiques à la version précédente.
- Test de compatibilité : un ancien `result_json` (sans nouveaux champs) reste lisible.
