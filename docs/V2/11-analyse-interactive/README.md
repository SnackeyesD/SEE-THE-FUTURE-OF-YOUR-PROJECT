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
- Protocole `1.11.0` : méthodes asynchrones `simulation.surface`, `simulation.goalseek` + notifications.
- UI : formulaire d'objectif, application en un clic, heatmap 2D, tornado interactif.
- Tests analytiques, budget et annulation.
- Budgets mesurés et consignés.

**Exclu**

- La vue 3D (phase 14) — la heatmap 2D est l'équivalent obligatoire.
- L'explication LLM (phase 12).

## 3. Livrables

- [ ] `engine/surface.py` et `engine/goal_seek.py`.
- [ ] Protocole `1.11.0`, types générés.
- [ ] `sidecar` : handlers asynchrones surface/goalseek.
- [ ] `components/cockpit/Heatmap.tsx`, `Tornado.tsx`, `GoalSeekPanel.tsx`.
- [ ] Tests moteur, sidecar, UI.
- [ ] `docs/perf/surface-goalseek.md` avec les mesures.

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

- [ ] `AxisSpec` : clé d'hypothèse, min, max, échelle (`linear` uniquement en V3).
- [ ] Valeurs de grille : `linspace` inclusif, 15 valeurs par défaut.
- [ ] Pour chaque point, réutiliser la **même banque de tirages** (CRN) et remplacer les paramètres de l'axe.
- [ ] Métriques supportées : `profit_p50`, `profit_p10`, `profit_p90`, `break_even_months_p50`, `financing_need_p90`, `loss_probability`.
- [ ] Retour : `xValues`, `yValues`, `zP50` (matrice), `zP10`/`zP90` optionnels, point courant, `metric`, `runs`, `seed`.
- [ ] Progression : notification par ligne ou tous les 10 points ; annulation entre points.
- [ ] Budget par défaut : 15×15 × 200 = 45 000 runs ; mesurer.
- [ ] Ne pas appeler `simulate()` par point si le coût de setup domine : boucle interne sur la grille, agrégats allégés.

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

- [ ] La métrique est évaluée par le moteur, jamais par l'UI.
- [ ] **Un levier** :
  - tester les bornes ; si la cible n'est pas encadrée, retourner le meilleur point ;
  - si la métrique est monotone sur l'intervalle (vérifié par échantillons), dichotomie ;
  - sinon, balayage grossier (10 points) puis raffinement local.
- [ ] **Plusieurs leviers** : recherche par coordonnées avec pas décroissant (compass search), pas de Nelder-Mead.
- [ ] Contraintes : bornes du modèle (`InputSpec`) ∩ bornes de l'hypothèse ; verrous exclus.
- [ ] Qualité : évaluations en `draft` (500 runs), confirmation en `final` (5 000) sur le meilleur point.
- [ ] Budget strict `max_evaluations` ; arrêt anticipé si tolérance atteinte.
- [ ] Retour :
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
- [ ] Si infaisable : message clair, meilleur compromis, ne pas prétendre avoir réussi.
- [ ] Annulation entre évaluations.

### Lot C — Protocole et sidecar

- [ ] `simulation.surface` : `{projectId, scenario, axisX, axisY, metric, grid, runs, seed}` → `{jobId}`.
- [ ] `simulation.goalseek` : `{projectId, scenario, objective, levers, locked, seed}` → `{jobId}`.
- [ ] Notifications : `simulation.progress` (jobId), `simulation.surface.partial` (lignes calculées), `simulation.done` (résultat), `simulation.cancelled`, `simulation.error`.
- [ ] Budget mémoire : pas de stockage de toutes les trajectoires.
- [ ] Job de surface/goalseek **annulable** et **remplaçable** par un nouveau job du même projet.
- [ ] Bump protocole `1.11.0`.

### Lot D — Heatmap 2D

- [ ] `Heatmap` : canvas ou SVG, axes X/Y avec unités et bornes, échelle de couleur issue des tokens.
- [ ] Couleurs séquentielles accessibles (pas rouge/vert seuls) ; légende avec valeurs.
- [ ] Point courant marqué et libellé.
- [ ] Survol : valeur de la métrique, coordonnées.
- [ ] Clic : règle les deux paramètres via une **commande** (phase 08) ; confirmation visuelle.
- [ ] Isolignes optionnelles (marching squares) ; pas obligatoires pour le jalon B.
- [ ] Bouton « recalculer la surface » ; jamais de calcul automatique à chaque pixel.
- [ ] Afficher le coût : `grille × runs`, graine, date.
- [ ] Tableau alternatif pour l'accessibilité.

### Lot E — Tornado interactif

- [ ] Réutiliser `sensitivity` du résultat ; libellé par hypothèse, contribution en %.
- [ ] Clic sur une barre : focus et scroll du panneau d'hypothèses ; pas de modification.
- [ ] Trier par contribution décroissante ; afficher la corrélation et la contribution.
- [ ] Avertir que la sensibilité est une corrélation, pas une causalité (info-bulle).

### Lot F — UI objectif

- [ ] Formulaire : métrique, comparateur, cible, leviers (cases + bornes), affichage des verrous.
- [ ] Progression et annulation.
- [ ] Résultat : valeurs proposées, métrique obtenue, faisabilité, écart.
- [ ] « Appliquer comme nouvelle branche » : crée une branche (phase 07) avec les valeurs proposées, même graine, et lance un `final`.
- [ ] Si infaisable : message explicite + bouton « appliquer le meilleur compromis ».
- [ ] Aucun nombre proposé n'est calculé hors moteur.

### Lot G — Tests

- [ ] Surface déterministe : même graine → même matrice.
- [ ] Surface : point courant présent, dimensions correctes, annulation.
- [ ] Goal seek analytique : métrique linéaire `a·prix + b·coût`, solution connue.
- [ ] Goal seek monotone : dichotomie converge en < budget.
- [ ] Goal seek non monotone : balayage + raffinement.
- [ ] Infeasible : `feasible=false`, gap correct.
- [ ] Budget : jamais plus d'évaluations que demandé.
- [ ] Annulation : < 200 ms.
- [ ] Heatmap : mapping valeur → couleur, clic → commande.
- [ ] Contrat : protocole `1.11.0`.

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

- [ ] Une surface 15×15 × 200 se calcule en ≤ 8 s sur machine modeste, avec progression et annulation.
- [ ] La heatmap est lisible, accessible et cliquable.
- [ ] Le tornado focalise le bon paramètre.
- [ ] L'objectif converge sur un cas analytique et gère l'infaisabilité.
- [ ] Le résultat est applicable en un clic comme nouvelle branche.
- [ ] Aucun chiffre n'est inventé : tout vient du moteur.
- [ ] Les budgets sont mesurés et consignés.

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

- [ ] Surface, goal seek, heatmap et tornado livrés.
- [ ] Protocole `1.11.0` généré.
- [ ] Tests analytiques et budgets verts.
- [ ] « Appliquer comme branche » fonctionne.
- [ ] Jalon B validé.
