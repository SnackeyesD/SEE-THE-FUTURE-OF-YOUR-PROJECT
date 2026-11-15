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

- [x] `SimulationOptions` / profils `draft` et `final`.
- [x] `CancelToken` (coopératif, thread-safe).
- [x] `PartialAggregates` et callback.
- [x] `ConvergenceState` exposé dans le résultat.
- [x] `SimulationCancelled` typée.
- [x] Tests de latence, de préfixe et de convergence.
- [x] Documentation des profils et des seuils.

## 4. Tâches détaillées

### Lot A — API et profils

- [x] Signature cible, en conservant l'ancien appel `simulate(scenario, config, progress=...)` :
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
- [x] Profils :
  | Qualité | Runs | Bloc | Usage |
  |---|---|---|---|
  | `draft` | 500 | 256 | Glissement, aperçu |
  | `final` | 5 000 | 256 | Relâchement, persistance |
- [x] `SimulationConfig.runs` reste prioritaire si fourni explicitement ; documenter la précédence.
- [x] Ne jamais dépasser 1 000 000 de runs dans le cockpit.

### Lot B — Annulation

- [x] `CancelToken` :
  ```python
  class CancelToken:
      def cancel(self) -> None: ...
      def is_cancelled(self) -> bool: ...
  ```
  Implémentation `threading.Event`, réutilisable par le sidecar.
- [x] Vérifier le jeton **entre chaque bloc**, jamais au milieu d'un bloc (trop coûteux).
- [x] Si annulé : lever `SimulationCancelled` après avoir cessé tout travail ; ne pas publier de partiel supplémentaire.
- [x] Taille de bloc 256 : un bloc 36 mois doit rester < 30 ms sur machine modeste pour tenir l'objectif < 100 ms.
- [x] Mesurer la latence réelle : `cancel()` → retour de la fonction.

### Lot C — Partiels

- [x] Après chaque bloc, calculer `PartialAggregates` :
  - métriques principales (P10/P50/P90 profit, point mort, trésorerie) ;
  - bandes mensuelles profit/trésorerie ;
  - histogramme ;
  - `completed_runs`, `total_runs`, `convergence`.
- [x] **Bornes d'histogramme fixes** : les dériver du premier bloc, puis n'étendre que si une valeur sort de la plage (élargissement symétrique documenté). Un histogramme qui change de bornes à chaque bloc est un bug visuel.
- [x] Les partiels ne contiennent **jamais** de trajectoires ni de paramètres par run.
- [x] Coalescer côté moteur n'est pas nécessaire ; le sidecar limitera à ~1 message / 50 ms (phase 06).
- [x] Ne pas persister un partiel.

### Lot D — Convergence

- [x] Calculer à chaque bloc un vecteur stable : `[p10_profit, p50_profit, p90_profit, break_even_probability, min_cash_p50]`.
- [x] Variation relative par rapport au bloc précédent, avec dénominateur protégé (`max(abs(x), epsilon)`).
- [x] `converged = True` si la variation max < 2 % sur **3 blocs consécutifs** et si `completed_runs ≥ 2 000` pour un `final` ; pour un `draft`, 2 blocs consécutifs et `completed_runs ≥ 500` suffisent (un draft de 500 runs n'a que 2 blocs).
- [x] Ne jamais afficher « convergé » pour un calcul de moins de 2 blocs complets.
- [x] Exposer aussi `stability` (0–1) pour l'affichage, sans promettre une précision illusoire.
- [x] Un `final` peut ne jamais converger : l'afficher, ne pas bloquer.

### Lot E — Tests

- [x] `test_cancel_latency` : 5 000 runs, annulation après ~2 blocs → < 100 ms sur machine de référence.
- [x] `test_cancel_raises` : `SimulationCancelled`, aucun callback après annulation.
- [x] `test_progress_monotonic` : progression croissante, dernier appel = 1.0 pour un calcul non annulé.
- [x] `test_draft_is_prefix_of_final` : le profit des 500 premiers runs du `final` est identique au `draft`.
- [x] `test_partial_histogram_bounds_stable` : bornes identiques entre partiels successifs (hors extension justifiée).
- [x] `test_convergence_flag` : converge sur un scénario simple ; ne converge pas sur 256 runs.
- [x] `test_partial_payload_size` : < 50 Ko par partiel.

## 5. Contrats

```python
class ConvergenceState(CamelModel):  # sérialisé en camelCase pour l'IPC
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

- [x] Un calcul `draft` 500 × 36 se termine en ≤ 50 ms sur la machine de référence.
- [x] Un `final` 5 000 × 36 se termine en ≤ 400 ms.
- [x] L'annulation revient en ≤ 100 ms.
- [x] Les partiels sont exploitables pour tracer un éventail et des KPI.
- [x] Le `draft` est un préfixe exact du `final`.
- [x] La convergence est exposée et testée, sans surpromesse.

## 8. Performance

| Mesure | Cible | Plafond | Mesuré (phase 04) |
|---|---|---|---|
| `draft` 500 × 36 | 50 ms | 150 ms | 18–26 ms |
| `final` 5 000 × 36 | 400 ms | 1,5 s | 150–170 ms |
| Latence d'annulation | 60 ms | 100 ms | 0,17 ms (max 0,19 ms) |
| Partiel | ≤ 10 ms de calcul | 30 ms | 7–9 ms médian, ≤ 19 ms max |
| Taille d'un partiel | < 50 Ko | 500 Ko | 26,1 Ko |

Machine de référence : Intel Pentium 6405U, 7,7 Go de RAM, Python 3.14, NumPy 2.5 ;
mesures `npm run bench:engine` sur le scénario exemple porté à 36 mois.

## 9. Risques

| Risque | Mitigation |
|---|---|
| Bloc trop gros → annulation lente | Bloc 256, mesuré sur machine modeste |
| Partiels trop fréquents → IPC saturé | Limitation côté sidecar (phase 06) |
| Convergence trompeuse | Seuil 2 % / transitions du profil + libellé explicite |
| Régressions de préfixe | Test croisé draft/final |

## 10. Definition of Done

- [x] API progressive, rétrocompatible, documentée.
- [x] Annulation et partiels testés.
- [x] Budgets mesurés et consignés.
- [x] La phase 06 peut brancher le worker sans modifier le moteur.

## 11. Notes d'implémentation

- **Modules** : `engine/progressive.py` porte `CancelToken`,
  `ConvergenceTracker`, `ConvergenceState` (dans `scenario.py`), les profils et
  `PartialAggregates`. `engine/runner.py` orchestre la boucle par blocs ;
  `engine/aggregation.py` construit les partiels et les bornes stables.
- **Précédence** : `resolve_execution()` lit `SimulationConfig.model_fields_set`.
  Seuls les champs explicitement fournis écrasent le profil ; les valeurs par
  défaut de `SimulationConfig` restent inchangées pour les autres usages.
- **Taille de bloc adaptative** : le profil fournit 256 runs. Pour de très
  grands calculs, le bloc est élargi jusqu'à 2 048 runs afin de rester sous 64
  blocs et d'éviter des centaines d'appels de modèle. Un `batchSize` explicite
  n'est jamais élargi.
- **Échantillonnage progressif** : les hypothèses et le bruit sont tirés bloc par
  bloc via `DrawBank.take_range()`. Le préfixe reste identique à un calcul de
  bout en bout, mais le moteur peut s'arrêter entre deux blocs.
- **Cadence des partiels** : premier bloc et dernier bloc toujours publiés, puis
  au plus 64 messages espacés régulièrement. La convergence, elle, est
  recalculée à chaque bloc sur au plus 2 000 runs. Les métriques d'un partiel
  utilisent au plus 5 000 runs et ses bandes mensuelles au plus 1 000 runs.
- **Bornes d'histogramme** : les partiels partagent une plage à centre fixe,
  élargie symétriquement avec 2 % de marge. Le résultat final conserve les
  bornes min/max de tous les runs : c'est ce qui garde l'invariance au
  `batchSize` testée depuis la phase 02.
- **Convergence** : le profil `final` exige deux transitions stables
  consécutives (trois états de blocs) et 2 000 runs ; le profil `draft` exige
  une transition (deux blocs) et 500 runs. Un calcul d'un seul bloc n'est jamais
  convergé.
- **Protocole** : `quality` et `convergence` sont optionnels dans
  `SimulationResult` (version `1.8.0` conservée). Le sidecar pourra les exposer
  tel quel en phase 06.
- **Tests** : `packages/engine/tests/test_progressive.py` couvre les profils, le
  préfixe, la progression, l'annulation et sa latence, la stabilité des bornes,
  la convergence et la taille des partiels.
- **Banc** : `bench_engine.py` mesure désormais les profils, la latence
  d'annulation, le coût et la taille des partiels, ainsi que la convergence.
