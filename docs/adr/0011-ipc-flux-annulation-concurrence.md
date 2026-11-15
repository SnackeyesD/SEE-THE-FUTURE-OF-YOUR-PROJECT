# ADR 0011 — IPC de flux, annulation et concurrence

- **Statut** : accepté
- **Date** : 2026-11-14
- **Contexte** : phase 01, s'applique en phase 06
- **Complète** : ADR 0002 (JSON-RPC 2.0 NDJSON sur stdio, conservé)

## Décision

Le calcul interactif devient un **job asynchrone** identifié par `runId`, avec notifications ordonnées et annulation coopérative.

### Côté protocole

- Méthodes :
  - `simulation.start {projectId, scenario, config?, quality, seed, runToken?}` → `{runId, accepted, replacedRunId?}` ;
  - `simulation.cancel {runId}` → `{cancelled}`.
- Notifications :
  - `simulation.progress {runId, completedRuns, totalRuns, fraction, block, convergence}` ;
  - `simulation.partial {runId, seq, aggregates}` ;
  - `simulation.done {runId, seq, result, persisted}` ;
  - `simulation.cancelled {runId, reason}` ;
  - `simulation.error {runId, code, message, retryable}`.
- `seq` est strictement croissant **par `runId`**, commence à 1, et `done`/`cancelled`/`error` est toujours le dernier message du run.
- Taille : un message ≤ 1 Mio ; un `partial` ≤ 500 Kio ; pas de trajectoires dans un partiel.
- Version protocole : `1.10.0` (après `1.8.0` en phase 02 et `1.9.0` en phase 05).

### Côté sidecar

- Un `SimulationService` possédé par `RpcServer` :
  - **un seul worker** de calcul ;
  - file de jobs et `RunRegistry` (`runId → {status, cancel_token, created_at, last_seq, quality, result?}`) ;
  - un `start` pour le même projet **annule** le job actif et les jobs en attente du projet (remplacement) ;
  - TTL 15 min, plafond 20 runs, éviction LRU des résultats non épinglés.
- **Writer unique** : toutes les écritures stdout passent par un seul point sérialisé (`write_all` + `\n` + flush). File sortante bornée (512 messages) ; en saturation, jeter les `partial` les plus anciens, jamais `done`/`cancelled`/`error`. Compteur de messages jetés exposé dans `health`.
- **Annulation** : `simulation.cancel` positionne un `CancelToken` (threading.Event) et répond immédiatement. Le moteur vérifie le jeton entre blocs de 256 et lève `SimulationCancelled`.
- **Persistance** : le worker ne touche jamais à SQLite. Un `draft` n'est **jamais** persisté. Un `final` est renvoyé au thread principal, qui persiste une seule fois (idempotence par `runId`).
- **Lectures rapides** (`ping`, `health`, `project.list`) restent servies par le thread principal pendant un calcul.
- **Arrêt** : annuler tous les jobs, vider la file, joindre le worker avec timeout de 2 s, fermer.

### Côté Rust

- Séparer le **superviseur** (démarrage/arrêt du process) du **handle de communication**.
- `SidecarHandle` :
  ```rust
  struct SidecarHandle {
      writer: Mutex<ChildStdin>,
      pending: Mutex<HashMap<u64, oneshot::Sender<RpcOutcome>>>,
      next_id: AtomicU64,
      app: AppHandle,
  }
  ```
- Le thread lecteur résout le `oneshot` correspondant à `id`, ou émet `simulation:event` pour une notification.
- `request()` ne tient **jamais** le verrou global pendant l'attente ; il attend sur un `oneshot` avec timeout.
- Timeouts : `ping`/`health` 5 s, `simulation.start` 10 s, `simulation.cancel` 2 s. Plus de timeout de 600 s pour une simulation interactive.
- Redémarrage : tous les `pending` échouent avec une erreur explicite ; l'UI reçoit un événement de statut ; les runs en cours sont invalidés.

### Côté TypeScript

- Un seul abonnement `listen("simulation:event")` par application, dans le futur store (phase 08).
- Filtrage obligatoire : ignorer un événement dont `runId !== activeRunId` ou `seq <= lastSeq` ; ne garder qu'un `partial` par frame.
- Aucun composant ne s'abonne directement.

## Contexte et raisons

- `rpc.py:604-611` est mono-thread : mesuré, un `ping` attend **≈ 700 ms** pendant un calcul (669–759 ms selon l'exécution).
- `sidecar.rs:206-282` attend la réponse en tenant le `Mutex` Tauri (`lib.rs:172-184`) ; seule `simulate.progress` est relayée.
- Le timeout simulation est de 600 s (`sidecar.rs:15-18`) : une annulation est impossible.
- Sans `runId` ni `seq`, un partiel périmé peut écraser un résultat plus récent.

## Alternatives

- **Threads multiples dans le sidecar** : complexité de concurrence et d'écriture ; un worker + writer sérialisé suffit.
- **HTTP local** : rouvre un port et une surface d'attaque ; non nécessaire.
- **Garder le Mutex Tauri** : incompatible avec l'annulation et les notifications.
- **Tout passer par SQLite** : latence et contention ; les brouillons n'ont pas à être persistés.

## Conséquences

- Le protocole change de version mineure ; les types TS/Python sont régénérés et `protocol:check` est obligatoire.
- L'UI doit gérer les états `idle → drafting → finalizing → idle | error` et ignorer les messages périmés.
- Un `final` peut être perdu si l'application se ferme avant persistance : c'est acceptable, le run reste relançable.
- Le débit de partiels est limité côté sidecar (~1 / 50 ms), pas côté UI.
- Les tests de charge deviennent obligatoires (100 partiels, 10 changements en 2 s, mémoire après 20 runs).

## Vérification

- Un `ping` répond pendant un `final` de 5 000 runs.
- Deux `start` successifs : le premier reçoit `cancelled`/`superseded`, le second seul émet des partiels.
- `cancel` de bout en bout < 150 ms.
- Aucun `partial` après `done`/`cancelled`.
- Aucun `draft` en base.

## Amendement phase 04 (2026-11-15)

Le contrat côté moteur est implémenté avant le worker de la phase 06.

- `engine.CancelToken` encapsule un `threading.Event` : `cancel()` et
  `is_cancelled()` sont sûrs entre threads, `reset()` réarme le jeton.
- `simulate(..., cancel=token)` vérifie le jeton **entre deux blocs** ; un bloc
  interrompu est terminé puis abandonné, sans publier de partiel. L'annulation
  lève `SimulationCancelled(completed_runs, total_runs)`.
- Les profils `draft`/`final` utilisent un bloc de 256 runs, ce qui borne la
  latence. Pour les calculs beaucoup plus grands, le bloc est élargi jusqu'à
  2 048 runs (au plus 64 blocs) afin d'éviter un surcoût d'appels de modèle
  sans dépasser le budget d'annulation. Mesure de référence : 0,17 ms médian
  (0,19 ms max) entre `cancel()` et le retour du moteur après 512 runs.
- Les partiels (`PartialAggregates`) et la progression sont des callbacks
  synchrones du moteur. La phase 06 conserve la responsabilité du worker, de
  la sérialisation JSON-RPC, de `seq` et de la limitation à ~1 partiel / 50 ms.
