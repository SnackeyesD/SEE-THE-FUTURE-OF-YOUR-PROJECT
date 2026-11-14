# Phase 04 — Calcul progressif & annulation

> **Objectif** : calculer par blocs, publier des agrégats partiels pendant le geste, annuler en moins de 100 ms, et exposer un indicateur de convergence honnête. C'est ce qui rend le cockpit « vivant » sans bloquer le sidecar.

**Références** : `V3-COCKPIT.md` §3.2, I1–I2 ; plan maître C3, C7, C8.
**Dépend de** : phases 02 (métriques) et 03 (tirages).
**Débloque** : 06, 09, 11.
**Profil** : senior Python ; 3–4 jours.

---

## 1. Contexte

Aujourd'hui `simulate()` est une fonction bloquante qui rend un résultat complet à la fin. Le sidecar ne peut ni publier d'état intermédiaire, ni interrompre un calcul. La V3 a besoin de :

- deux qualités : `draft` (rapide, pendant le glissement) et `final` (au relâchement) ;
- des notifications de progression et des agrégats partiels ;
- une annulation coopérative ;
- un indicateur de convergence lisible (pas un faux « 100 % »).

## 2. Périmètre

**Inclus**

- API `simulate()` étendue, rétrocompatible.
- Profils de qualité.
- Boucle par blocs avec `on_progress`, `on_partial`, `cancel`.
- Agrégats partiels stables (histogramme à bornes fixes, bandes mensuelles).
- Indicateur de convergence.
- Tests de latence d'annulation et de préfixe entre qualités.

**Exclu**

- Threads, files et protocole (phase 06).
- Événements (phase 05).
- Surface et goal seek (phase 11), qui réutiliseront l'API.

## 3. Livrables

- [ ] `SimulationOptions` / profils `draft` et `final`.
- [ ] `CancelToken` (coopératif, thread-safe).
- [ ] `PartialAggregates` et callback.
- [ ] `ConvergenceState` exposé dans le résultat.
- [ ] `SimulationCancelled` typée.
- [ ] Tests de latence, de préfixe et de convergence.
- [ ] Documentation des profils et des seuils.

## 4. Tâches détaillées

### Lot A — API et profils

- [ ] Signature cible, en conservant l'ancien appel `simulate(scenario, config, progress=...)` :
  ```python
  def simulate(
      scenario: Scenario,
      config: SimulationConfig | None = None,
      *,
      progress: ProgressCallback | None = None,      # compatibilité
      quality: Literal["draft", "final"] = "final",
      on_progress: ProgressCallback | None = None,
      on_partial: PartialCallback | None = None,
      cancel: CancelToken | None = None,
  ) -> SimulationResult: ...
  ```
- [ ] Profils :
  | Qualité | Runs | Bloc | Usage |
  |---|---|---|---|
  | `draft` | 500 | 256 | Glissement, aperçu |
  | `final` | 5 000 | 256 | Relâchement, persistance |
- [ ] `SimulationConfig.runs` reste prioritaire si fourni explicitement ; documenter la précédence.
- [ ] Ne jamais dépasser 1 000 000 de runs dans le cockpit.

### Lot B — Annulation

- [ ] `CancelToken` :
  ```python
  class CancelToken:
      def cancel(self) -> None: ...
      def is_cancelled(self) -> bool: ...
  ```
  Implémentation `threading.Event`, réutilisable par le sidecar.
- [ ] Vérifier le jeton **entre chaque bloc**, jamais au milieu d'un bloc (trop coûteux).
- [ ] Si annulé : lever `SimulationCancelled` après avoir cessé tout travail ; ne pas publier de partiel supplémentaire.
- [ ] Taille de bloc 256 : un bloc 36 mois doit rester < 30 ms sur machine modeste pour tenir l'objectif < 100 ms.
- [ ] Mesurer la latence réelle : `cancel()` → retour de la fonction.

### Lot C — Partiels

- [ ] Après chaque bloc, calculer `PartialAggregates` :
  - métriques principales (P10/P50/P90 profit, point mort, trésorerie) ;
  - bandes mensuelles profit/trésorerie ;
  - histogramme ;
  - `completed_runs`, `total_runs`, `convergence`.
- [ ] **Bornes d'histogramme fixes** : les dériver du premier bloc, puis n'étendre que si une valeur sort de la plage (élargissement symétrique documenté). Un histogramme qui change de bornes à chaque bloc est un bug visuel.
- [ ] Les partiels ne contiennent **jamais** de trajectoires ni de paramètres par run.
- [ ] Coalescer côté moteur n'est pas nécessaire ; le sidecar limitera à ~1 message / 50 ms (phase 06).
- [ ] Ne pas persister un partiel.

### Lot D — Convergence

- [ ] Calculer à chaque bloc un vecteur stable : `[p10_profit, p50_profit, p90_profit, break_even_probability, min_cash_p50]`.
- [ ] Variation relative par rapport au bloc précédent, avec dénominateur protégé (`max(abs(x), epsilon)`).
- [ ] `converged = True` si la variation max < 2 % sur **3 blocs consécutifs** et si `completed_runs ≥ 2 000` pour un `final` ; pour un `draft`, 2 blocs consécutifs et `completed_runs ≥ 500` suffisent (un draft de 500 runs n'a que 2 blocs).
- [ ] Ne jamais afficher « convergé » pour un calcul de moins de 2 blocs complets.
- [ ] Exposer aussi `stability` (0–1) pour l'affichage, sans promettre une précision illusoire.
- [ ] Un `final` peut ne jamais converger : l'afficher, ne pas bloquer.

### Lot E — Tests

- [ ] `test_cancel_latency` : 5 000 runs, annulation après ~2 blocs → < 100 ms sur machine de référence.
- [ ] `test_cancel_raises` : `SimulationCancelled`, aucun callback après annulation.
- [ ] `test_progress_monotonic` : progression croissante, dernier appel = 1.0 pour un calcul non annulé.
- [ ] `test_draft_is_prefix_of_final` : le profit des 500 premiers runs du `final` est identique au `draft`.
- [ ] `test_partial_histogram_bounds_stable` : bornes identiques entre partiels successifs (hors extension justifiée).
- [ ] `test_convergence_flag` : converge sur un scénario simple ; ne converge pas sur 256 runs.
- [ ] `test_partial_payload_size` : < 50 Ko par partiel.

## 5. Contrats

```python
@dataclass(frozen=True)
class ConvergenceState:
    converged: bool
    stability: float          # 0–1
    max_relative_change: float
    stable_blocks: int


@dataclass(frozen=True)
class PartialAggregates:
    completed_runs: int
    total_runs: int
    metrics: Metrics
    histogram: Histogram
    monthly: MonthlyAverages
    convergence: ConvergenceState
```

```python
class SimulationCancelled(EngineError):
    """Calcul interrompu par l'utilisateur ou par un nouveau run."""
```

## 6. Pièges

- **Ne pas recalculer les percentiles sur tous les runs à chaque bloc** : utiliser l'échantillon de la phase 02 et, au-delà, plafonner la fréquence des partiels.
- **Ne pas annuler au milieu d'un bloc** : le coût de vérification dépasse le gain ; 256 runs suffisent.
- **Ne pas afficher la convergence comme un pourcentage de précision** : c'est une stabilité observée, pas une garantie.
- **Ne pas changer les bornes d'histogramme** en cours de calcul : les barres « sautent ».
- **Ne pas publier de partiel après annulation** : le sidecar et l'UI ignorent déjà les runs périmés, mais le moteur ne doit pas en produire.
- **Le préfixe doit rester vrai** : `draft` et `final` partagent les mêmes 500 premiers runs.

## 7. Critères d'acceptation

- [ ] Un calcul `draft` 500 × 36 se termine en ≤ 50 ms sur la machine de référence.
- [ ] Un `final` 5 000 × 36 se termine en ≤ 400 ms.
- [ ] L'annulation revient en ≤ 100 ms.
- [ ] Les partiels sont exploitables pour tracer un éventail et des KPI.
- [ ] Le `draft` est un préfixe exact du `final`.
- [ ] La convergence est exposée et testée, sans surpromesse.

## 8. Performance

| Mesure | Cible | Plafond |
|---|---|---|
| `draft` 500 × 36 | 50 ms | 150 ms |
| `final` 5 000 × 36 | 400 ms | 1,5 s |
| Latence d'annulation | 60 ms | 100 ms |
| Partiel | ≤ 10 ms de calcul | 30 ms |
| Taille d'un partiel | < 50 Ko | 500 Ko |

## 9. Risques

| Risque | Mitigation |
|---|---|
| Bloc trop gros → annulation lente | Bloc 256, mesuré sur machine modeste |
| Partiels trop fréquents → IPC saturé | Limitation côté sidecar (phase 06) |
| Convergence trompeuse | Seuil 2 % / 3 blocs + libellé explicite |
| Régressions de préfixe | Test croisé draft/final |

## 10. Definition of Done

- [ ] API progressive, rétrocompatible, documentée.
- [ ] Annulation et partiels testés.
- [ ] Budgets mesurés et consignés.
- [ ] La phase 06 peut brancher le worker sans modifier le moteur.
