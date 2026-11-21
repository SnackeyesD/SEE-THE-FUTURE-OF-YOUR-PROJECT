# Phase 11 — Analyse interactive

> **Objectif** : passer de « je vois un résultat » à « je cherche une décision » : surface de résultat 2D, carte de chaleur, tornado interactif et recherche d'objectif (« je veux le point mort en 6 mois »).

**Références** : `V3-COCKPIT.md` §3.4–3.5, §7 (I6, I10, I11), §9 ; plan maître C7, C9.
**Dépend de** : phase 09 (cockpit, store), 03 (CRN), 05 (événements).
**Débloque** : 14 (3D), 15 (démo, pitch).
**Profil** : senior Python (surface/goal seek) + senior TS (heatmap/tornado) ; 7–8 jours.
**Jalon B** : un utilisateur peut dire « je veux le point mort en 6 mois » et obtenir des leviers concrets.

---

## 1. Contexte

La V3 doit répondre à trois questions :

1. **Où est la zone favorable ?** → surface 2D / heatmap sur deux paramètres.
2. **Quel levier compte le plus ?** → tornado interactif.
3. **Que faut-il changer pour atteindre un objectif ?** → recherche d'objectif.

Grâce aux tirages communs, la métrique est **déterministe à graine fixée**. Mais elle reste **en escalier** pour les probabilités : un algorithme dérivé (Nelder-Mead) est inadapté.

## 2. Périmètre

**Inclus**

- `surface()` moteur : grille 2D, CRN, progression, annulation.
- `goal_seek()` moteur : un ou plusieurs leviers, contraintes, budget, faisabilité.
- Protocole `1.12.0` : méthodes asynchrones `simulation.surface`, `simulation.goalseek` + notifications.
- UI : formulaire d'objectif, application en un clic, heatmap 2D, tornado interactif.
- Tests analytiques, budget et annulation.
- Budgets mesurés et consignés.

**Exclu**

- La vue 3D (phase 14) — la heatmap 2D est l'équivalent obligatoire.
- L'explication LLM (phase 12).

## 3. Livrables

- [x] `engine/surface.py` et `engine/goal_seek.py`.
- [x] Protocole `1.12.0`, types générés.
- [x] `sidecar` : handlers asynchrones surface/goalseek.
- [x] `components/cockpit/Heatmap.tsx`, `Tornado.tsx`, `GoalSeekPanel.tsx`, `SurfacePanel.tsx`.
- [x] Tests moteur, sidecar, UI.
- [x] `docs/perf/surface-goalseek.md` avec les mesures.

## 4. Tâches détaillées

### Lot A — Surface moteur

```python
def surface(
    scenario: Scenario,
    config: SimulationConfig,
    axis_x: AxisSpec,
    axis_y: AxisSpec,
    metric: SurfaceMetric = "profit_p50",
    grid: tuple[int, int] = (15, 15),
    runs: int = 200,
    seed: int | None = None,
    on_progress: ProgressCallback | None = None,
    cancel: CancelToken | None = None,
) -> SurfaceResult: ...
```

- [x] `AxisSpec` : clé d'hypothèse, min, max, échelle (`linear` uniquement en V3).
- [x] Valeurs de grille : `linspace` inclusif, 15 valeurs par défaut.
- [x] Pour chaque point, réutiliser la **même banque de tirages** (CRN) et remplacer les paramètres de l'axe.
- [x] Métriques supportées : `profit_p50`, `profit_p10`, `profit_p90`, `break_even_months_p50`, `financing_need_p90`, `loss_probability`.
- [x] Retour : `xValues`, `yValues`, `zP50` (matrice), `zP10`/`zP90` optionnels, point courant, `metric`, `runs`, `seed`.
- [x] Progression : notification par ligne ou tous les 10 points ; annulation entre points.
- [x] Budget par défaut : 15×15 × 200 = 45 000 runs ; mesuré à 1,504 s.
- [x] Ne pas appeler `simulate()` par point si le coût de setup domine : boucle interne sur la grille, agrégats allégés.

### Lot B — Recherche d'objectif

```python
@dataclass(frozen=True)
class Objective:
    metric: str
    comparator: Literal[">=", "<="]
    target: float
    tolerance: float = 0.02

@dataclass(frozen=True)
class Lever:
    key: str
    minimum: float
    maximum: float

def goal_seek(
    scenario: Scenario,
    objective: Objective,
    levers: list[Lever],
    *,
    locked: set[str],
    seed: int,
    max_evaluations: int = 80,
    cancel: CancelToken | None = None,
) -> GoalSeekResult: ...
```

- [x] La métrique est évaluée par le moteur, jamais par l'UI.
- [x] **Un levier** :
  - tester les bornes ; si la cible n'est pas encadrée, retourner le meilleur point ;
  - si la métrique est monotone sur l'intervalle (vérifié par échantillons), dichotomie ;
  - sinon, balayage grossier (10 points) puis raffinement local.
- [x] **Plusieurs leviers** : recherche par coordonnées avec pas décroissant (compass search), pas de Nelder-Mead.
- [x] Contraintes : bornes du modèle (`InputSpec`) ∩ bornes de l'hypothèse ; verrous exclus.
- [x] Qualité : évaluations en `draft` (500 runs), confirmation en `final` (5 000) sur le meilleur point.
- [x] Budget strict `max_evaluations` ; arrêt anticipé si tolérance atteinte.
- [x] Retour :
  ```ts
  type GoalSeekResult = {
    feasible: boolean;
    best: Record<string, number>;
    achieved: number;
    target: number;
    gap: number;
    evaluations: number;
    trace: Array<{ point: Record<string, number>; value: number }>;
  };
  ```
- [x] Si infaisable : message clair, meilleur compromis, ne pas prétendre avoir réussi.
- [x] Annulation entre évaluations.

### Lot C — Protocole et sidecar

- [x] `simulation.surface` : `{projectId, scenario, axisX, axisY, metric, grid, runs, seed}` → `{jobId}`.
- [x] `simulation.goalseek` : `{projectId, scenario, objective, levers, locked, seed}` → `{jobId}`.
- [x] Notifications : `simulation.progress` (jobId), `simulation.surface.partial` (lignes calculées), `simulation.done` (résultat), `simulation.cancelled`, `simulation.error`.
- [x] Budget mémoire : pas de stockage de toutes les trajectoires.
- [x] Job de surface/goalseek **annulable** et **remplaçable** par un nouveau job du même projet.
- [x] Bump protocole `1.12.0`.

### Lot D — Heatmap 2D

- [x] `Heatmap` : grille HTML accessible, axes X/Y avec unités et bornes, échelle de couleur issue des tokens.
- [x] Couleurs séquentielles accessibles (pas rouge/vert seuls) ; légende avec valeurs.
- [x] Point courant marqué et libellé.
- [x] Survol : valeur de la métrique, coordonnées.
- [x] Clic : règle les deux paramètres via une **commande** (phase 08) ; confirmation visuelle.
- [ ] Isolignes optionnelles (marching squares) — non retenues pour le jalon B.
- [x] Bouton « recalculer la surface » ; jamais de calcul automatique à chaque pixel.
- [x] Afficher le coût : `grille × runs`, graine, durée moteur du résultat.
- [x] Tableau alternatif pour l'accessibilité.

### Lot E — Tornado interactif

- [x] Réutiliser `sensitivity` du résultat ; libellé par hypothèse, contribution en %.
- [x] Clic sur une barre : focus et scroll du panneau d'hypothèses ; pas de modification.
- [x] Trier par contribution décroissante ; afficher la corrélation et la contribution.
- [x] Avertir que la sensibilité est une corrélation, pas une causalité (description et info-bulle).

### Lot F — UI objectif

- [x] Formulaire : métrique, comparateur, cible, leviers (cases + bornes), affichage des verrous.
- [x] Progression et annulation.
- [x] Résultat : valeurs proposées, métrique obtenue, faisabilité, écart.
- [x] « Appliquer comme nouvelle branche » : crée une branche (phase 07) avec les valeurs proposées, même graine, et lance un `final`.
- [x] Si infaisable : message explicite + bouton « appliquer le meilleur compromis ».
- [x] Aucun nombre proposé n'est calculé hors moteur.

### Lot G — Tests

- [x] Surface déterministe : même graine → même matrice.
- [x] Surface : point courant présent, dimensions correctes, annulation.
- [x] Goal seek analytique : métrique linéaire `a·prix + b·coût`, solution connue.
- [x] Goal seek monotone : dichotomie converge en < budget.
- [x] Goal seek non monotone : balayage + raffinement.
- [x] Infeasible : `feasible=false`, gap correct.
- [x] Budget : jamais plus d'évaluations que demandé.
- [x] Annulation : jeton avant/pendant le calcul et intention honorée pendant l'attente de l'accusé de démarrage.
- [x] Heatmap : mapping valeur → couleur, clic → commande.
- [x] Contrat : protocole `1.12.0`.

## 5. Contrats

```python
@dataclass(frozen=True)
class AxisSpec:
    key: str
    minimum: float
    maximum: float
    scale: Literal["linear"] = "linear"

@dataclass(frozen=True)
class SurfaceResult:
    x_values: np.ndarray
    y_values: np.ndarray
    z_p50: np.ndarray          # shape (len(y), len(x))
    z_p10: np.ndarray | None
    z_p90: np.ndarray | None
    current: tuple[float, float]
    metric: str
    runs: int
    seed: int
```

Règles :

- L'axe X varie la colonne, l'axe Y la ligne ; documenter l'orientation pour éviter les transpositions.
- Les valeurs affichées sont celles du moteur, sans lissage.
- Une surface n'est jamais calculée pendant un glissement de curseur.
- Le coût (`grille × runs`) est visible avant lancement.

## 6. Pièges

- **Appeler `simulate()` 225 fois** : le coût de setup et d'agrégation domine ; boucler à l'intérieur.
- **Nelder-Mead sur une probabilité** : échoue sur les plateaux ; utiliser coordonnées/dichotomie.
- **Confondre « pas de solution » et « budget épuisé »** : deux messages différents.
- **Afficher la surface comme une prévision** : c'est une exploration conditionnelle aux hypothèses.
- **Heatmap transposée** : tester avec une métrique qui dépend d'un seul axe.
- **Appliquer un objectif sans branche** : écraserait le scénario courant ; toujours créer une branche.
- **Oublier la graine** : la surface et l'objectif doivent utiliser la graine affichée.

## 7. Critères d'acceptation

- [x] Une surface 15×15 × 200 se calcule en ≤ 8 s sur machine modeste, avec progression et annulation (1,504 s mesuré).
- [x] La heatmap est lisible, accessible et cliquable.
- [x] Le tornado focalise le bon paramètre.
- [x] L'objectif converge sur un cas analytique et gère l'infaisabilité.
- [x] Le résultat est applicable en un clic comme nouvelle branche.
- [x] Aucun chiffre n'est inventé : tout vient du moteur.
- [x] Les budgets sont mesurés et consignés.

## 8. Performance

| Mesure | Cible | Plafond |
|---|---|---|
| Surface 15×15 × 200 | 8 s | 20 s |
| Surface 25×25 × 300 (option) | 20 s | 45 s |
| Goal seek 80 évaluations `draft` | 3 s | 8 s |
| Confirmation `final` | 400 ms | 1,5 s |
| Heatmap 225 cellules | 16 ms | 33 ms |

## 9. Risques

| Risque | Mitigation |
|---|---|
| Surface trop lente | Grille réduite, runs réduits, mesure |
| Objectif instable | Métrique déterministe + recherche adaptée |
| Fausse promesse | Message d'infaisabilité explicite |
| Confusion corrélation/causalité | Info-bulle tornado |
| UI qui bloque | Jobs asynchrones, annulation |

## 10. Definition of Done

- [x] Surface, goal seek, heatmap et tornado livrés.
- [x] Protocole `1.12.0` généré.
- [x] Tests analytiques et budgets verts.
- [x] « Appliquer comme branche » fonctionne.
- [x] Jalon B validé sur le parcours de démonstration et les tests d'intégration.

## 11. Mise en œuvre

### Moteur

- `engine/surface.py` : `surface()` balaye la grille avec la même banque de tirages (CRN), remplace les deux hypothèses par `{ value }` et produit `zP50`, `zP10`/`zP90` selon la métrique. `z[ligneY][colonneX]` ; `current` vient des hypothèses du scénario.
- `engine/goal_seek.py` : un levier → balayage/dichotomie, plusieurs leviers → compass search. Aucun Nelder-Mead. Le budget ne compte que les évaluations de recherche ; la confirmation `final` est hors budget. `budgetExhausted` et `feasible` sont distincts, et `message` est produit par le moteur.

### Protocole et sidecar

- Protocole `1.12.0` : `simulation.surface`, `simulation.goalseek`, `simulation.cancel` (accepte `runId` ou `jobId`), `project.scenario.branch`.
- Notifications d'analyse : `simulation.progress`, `simulation.surface.partial`, `simulation.done`, `simulation.cancelled`, `simulation.error`, toutes identifiées par `jobId`.
- `analysis_service.py` : un job surface et un job objectif par projet, annulables et remplaçables. Les événements d'un job remplacé n'atteignent plus l'UI.
- `ipc.ts` : routage par `jobId`, rejeu des événements arrivés avant l'abonnement, abonnement créé avant l'invoke pour ne perdre aucun partiel.

### UI

- Cockpit : bouton « Analyse interactive », onglets « Surface 2D » et « Recherche d'objectif ». Les deux panneaux restent montés et masqués (`hidden`) : formulaires et résultats survivent aux changements d'onglet et à la fermeture/réouverture.
- Surface : coût `grille × runs`, graine, progression, annulation, heatmap cliquable avec tableau alternatif. Une cellule applique les deux valeurs au scénario comme le moteur (`{ value }`).
- Objectif : leviers verrouillés désactivés et exclus, repli automatique sur un levier disponible, budget `évaluations × runs` visible, résultat moteur affiché sans reformulation. Un objectif non atteint propose le meilleur compromis, jamais un faux « atteint ».
- Application : crée une branche via `project.scenario.branch`, applique le scénario puis lance `live.runFinal()` avec la graine du cockpit.
- Tornado : tri par contribution, corrélation en info-bulle, avertissement corrélation ≠ causalité, clic pour cibler l'hypothèse.

### Correctif de clôture — annulation pendant le démarrage

Un démarrage de surface ou d'objectif reste en attente de l'accusé `{ jobId }`. Une annulation demandée dans cet intervalle est désormais mémorisée : l'état passe à `cancelling`, puis le job est annulé dès que son `jobId` est connu, sans abonnement ni partiel tardif. Des générations par type d'analyse empêchent un démarrage remplacé d'écraser l'état du plus récent, et les mises à jour sont ignorées après démontage.

### Validation

| Suite | Résultat |
|---|---|
| Moteur (`pytest`) | 155 tests |
| Sidecar (`pytest`) | 60 tests |
| Desktop (`vitest`) | 168 tests |
| Tauri (`cargo test`) | 9 tests |
| `protocol:check`, `typecheck`, `lint`, `ui:check`, build web | verts |

Mesures détaillées : [`docs/perf/surface-goalseek.md`](../../perf/surface-goalseek.md).
