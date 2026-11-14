# Phase 06 — IPC de flux & concurrence

> **Objectif** : rendre le calcul réellement interactif de bout en bout. Le sidecar ne bloque plus sa lecture, le transport Rust n'attend plus en tenant un verrou, les notifications arrivent dans l'ordre, et l'annulation fonctionne.

**Références** : `V3-COCKPIT.md` §4, §5.3, I1 ; plan maître C3, C4, C5, C12, ADR 0011.
**Dépend de** : phase 04 (moteur progressif et annulable).
**Débloque** : 08, 09, 11, 12.
**Profil** : senior Python + senior Rust/TS ; 7–8 jours. **C'est la phase la plus risquée du plan.**

---

## 1. Contexte

Le chemin actuel est strictement séquentiel :

- `RpcServer.serve()` lit une ligne, exécute le handler, écrit la réponse ; un calcul long bloque toute lecture ;
- `SidecarManager::request_with` envoie une requête puis attend la réponse **en tenant le `Mutex`** exposé à Tauri ;
- les notifications qui ne concernent pas la requête courante sont ignorées (sauf le callback `simulate.progress`) ;
- `project.simulate` persiste le run complet avant de répondre ;
- `SIMULATION_TIMEOUT` rend l'annulation impossible.

Sans refonte, le cockpit ne peut pas afficher de partiels ni annuler.

## 2. Périmètre

**Inclus**

- Schéma protocole `simulation.start`, `simulation.cancel`, notifications de flux.
- Service de runs côté sidecar : worker, file, registre, writer sérialisé, TTL.
- Refonte du dispatcher Rust et des commandes Tauri.
- Wrapper IPC TypeScript, abonnement unique, filtrage des runs périmés.
- Politique de persistance : `draft` jamais persisté, `final` persisté sur le thread principal.
- Tests de concurrence, d'annulation, d'ordre et de charge.

**Exclu**

- `surface`, `goalseek`, `trajectories`, `provenance` (phases 11 et 12).
- Composants du cockpit (phase 09).

## 3. Livrables

- [ ] Protocole `1.10.0` : méthodes, notifications, types d'agrégats partiels.
- [ ] `sidecar/simulation_service.py` : worker, `RunRegistry`, `CancelToken`, throttling.
- [ ] `rpc.py` : handlers non bloquants, writer thread-safe, arrêt propre.
- [ ] `SidecarManager` Rust refondu (writer, pending, dispatcher).
- [ ] Commandes Tauri `simulation_start`, `simulation_cancel`.
- [ ] `apps/desktop/src/lib/ipc.ts` : `startSimulation`, `cancelSimulation`, `onSimulationEvent`.
- [ ] Tests Python, Rust, contrat, et test de charge.
- [ ] `docs/perf/ipc.md` avec latences mesurées.

## 4. Tâches détaillées

### Lot A — Protocole

- [ ] Méthodes :
  | Méthode | Params | Résultat |
  |---|---|---|
  | `simulation.start` | `{projectId, scenario, config?, quality, seed, runToken?}` | `{runId, accepted, replacedRunId?}` |
  | `simulation.cancel` | `{runId}` | `{cancelled}` |
- [ ] Notifications :
  | Notification | Contenu |
  |---|---|
  | `simulation.progress` | `{runId, completedRuns, totalRuns, fraction, block, convergence}` |
  | `simulation.partial` | `{runId, seq, aggregates}` |
  | `simulation.done` | `{runId, seq, result, persisted}` |
  | `simulation.cancelled` | `{runId, reason}` |
  | `simulation.error` | `{runId, code, message, retryable}` |
- [ ] `seq` strictement croissant par `runId`, commence à 0 ou 1 (documenté).
- [ ] `aggregates` réutilise les types de la phase 02 ; **jamais** de trajectoires dans un partiel.
- [ ] Limites : `simulation.start` répond en < 50 ms ; `partial` ≤ 500 Ko ; un message ≤ 1 Mo.
- [ ] Bump `1.10.0`, génération TS/Python, test Rust de version.

### Lot B — Service sidecar

- [ ] Créer un `SimulationService` possédé par `RpcServer` :
  - file de jobs (un seul worker) ;
  - `RunRegistry` : `runId → {status, cancel_token, created_at, last_seq, result?, quality}` ;
  - politique : un nouveau `start` pour le même projet **annule** le job actif et les jobs en attente du projet ;
  - TTL 15 min et plafond 20 runs ; éviction LRU des résultats non épinglés.
- [ ] Le worker appelle `engine.simulate(..., quality, on_partial, cancel)`.
- [ ] `on_progress` / `on_partial` : throttle à 50 ms, sérialisation via un **writer unique**.
- [ ] `simulation.cancel` : positionne le jeton, répond immédiatement ; le worker lève `SimulationCancelled`.
- [ ] **Persistance** :
  - `draft` : aucune écriture SQLite, aucun stockage disque ;
  - `final` : le worker renvoie le résultat au thread principal, qui persiste via `project_service` ; le worker ne touche pas à SQLite.
- [ ] Arrêt : annuler tous les jobs, vider la file, joindre le worker avec timeout (2 s), puis fermer.
- [ ] Les handlers de lecture rapide (`ping`, `health`, `project.list`) restent sur le thread principal et répondent pendant un calcul.

### Lot C — Writer et ordre

- [ ] Un seul point d'écriture stdout (`OutboundWriter`) protégé par un verrou ou une file dédiée.
- [ ] Chaque ligne JSON est écrite en une fois (`write_all` + `\n` + flush).
- [ ] File sortante bornée (ex. 512 messages) : en cas de saturation, **jeter les `partial` les plus anciens**, jamais `done`, `cancelled` ou `error`.
- [ ] Compteur de messages jetés exposé dans `health` (diagnostic).
- [ ] Tests d'ordre : `seq` croissant, `done` en dernier, pas de `partial` après `cancelled`.

### Lot D — Transport Rust

- [ ] Séparer le **superviseur** (démarrage/arrêt du process) du **handle** de communication.
- [ ] `SidecarHandle` :
  ```rust
  struct SidecarHandle {
      writer: Mutex<ChildStdin>,
      pending: Mutex<HashMap<u64, oneshot::Sender<RpcOutcome>>>,
      next_id: AtomicU64,
      app: AppHandle,
  }
  ```
- [ ] Thread lecteur : pour chaque ligne,
  - si `id` présent → résoudre le `oneshot` correspondant ;
  - si `method` présent → `app.emit("simulation:event", payload)` (une seule porte pour toutes les notifications).
- [ ] `request()` : enregistrer le oneshot, écrire, attendre avec timeout ; **ne jamais tenir le verrou global pendant l'attente**.
- [ ] `simulation_start` : requête courte, renvoie `runId` ; ne dépend pas de la durée du calcul.
- [ ] `simulation_cancel` : envoi best-effort, timeout 2 s.
- [ ] Timeouts : `ping`/`health` 5 s, `simulation.start` 10 s, `cancel` 2 s, provider/agent inchangés.
- [ ] Redémarrage du sidecar : tous les `pending` échouent avec une erreur explicite ; l'UI reçoit un événement de statut.
- [ ] Tests unitaires du dispatcher avec un faux canal ; tests d'intégration avec le vrai sidecar Python.

### Lot E — Wrapper TypeScript

- [ ] `startSimulation(params): Promise<SimulationStartResult>` via `invoke("simulation_start")`.
- [ ] `cancelSimulation(runId): Promise<void>`.
- [ ] `onSimulationEvent(handler): Promise<UnlistenFn>` : un seul `listen("simulation:event")` par application.
- [ ] Filtrage :
  - ignorer tout événement dont `runId` n'est pas le run actif ;
  - ignorer `seq ≤ lastSeq` ;
  - ne garder qu'un `partial` par frame d'animation.
- [ ] Aucun composant ne s'abonne directement ; l'abonnement vit dans le store (phase 08).
- [ ] En mode web (`dev:web`), un shim déterministe remplace Tauri pour les tests E2E.

### Lot F — Tests et charge

- [ ] Un `ping` répond pendant un `final` de 5 000 runs.
- [ ] Deux `start` successifs : le premier reçoit `cancelled`/`superseded`, le second seul émet des partiels.
- [ ] `cancel` : latence de bout en bout < 150 ms (moteur < 100 ms + transport).
- [ ] Aucun partiel après `cancelled`/`done`.
- [ ] 100 partiels simulés : pas de perte de `done`, pas de blocage du writer.
- [ ] Charge : 10 changements de paramètre en 2 s → au plus 1 job actif, pas d'accumulation.
- [ ] Mémoire du sidecar après 20 runs : ≤ 500 Mo.
- [ ] `protocol:check`, tests Rust, tests sidecar verts.

## 5. Contrats

```python
@dataclass
class Job:
    run_id: str
    project_id: str
    quality: str
    cancel: CancelToken
    seq: int = 0


class SimulationService:
    def start(self, params: dict, notify: Notifier) -> dict: ...
    def cancel(self, run_id: str) -> dict: ...
    def shutdown(self) -> None: ...
```

```ts
type SimulationEvent =
  | { method: "simulation.progress"; params: SimulationProgress }
  | { method: "simulation.partial"; params: SimulationPartial }
  | { method: "simulation.done"; params: SimulationDone }
  | { method: "simulation.cancelled"; params: SimulationCancelled }
  | { method: "simulation.error"; params: SimulationError };
```

Codes d'erreur : `simulation_invalid`, `simulation_busy`, `simulation_cancelled`, `simulation_superseded`, `simulation_failed`, `run_not_found`.

## 6. Pièges

- **Mutex Tauri tenu pendant l'attente** : c'est le défaut actuel ; il empêche tout parallélisme. Le verrou ne doit protéger que l'écriture et la map `pending`.
- **Écritures stdout concurrentes** : un seul writer, sinon lignes entrelacées.
- **SQLite depuis le worker** : garder la persistance sur le thread principal.
- **Notifications périmées** : filtrer par `runId` **et** `seq` côté UI ; ne pas se fier au seul ordre d'arrivée.
- **Throttle trop agressif** : 50 ms suffit ; 0 ms sature le stdio.
- **Annulation « logique »** : si le worker continue, la latence explose. Vérifier le jeton entre blocs.
- **Redémarrage** : un sidecar relancé doit invalider tous les runs en cours, pas les laisser pendants.

## 7. Critères d'acceptation

- [ ] Déplacer un curseur lance un `draft` et reçoit des partiels sans bloquer `ping`.
- [ ] Un nouveau `start` annule le précédent ; un seul run actif.
- [ ] `cancel` revient en < 150 ms de bout en bout.
- [ ] Aucun `draft` n'est écrit en base.
- [ ] Le `final` est persisté une seule fois, avec la bonne graine.
- [ ] Les notifications sont ordonnées et filtrables.
- [ ] Le transport Rust ne bloque plus les autres commandes.
- [ ] Tests de charge et de mémoire verts.

## 8. Performance

| Mesure | Cible | Plafond |
|---|---|---|
| Réponse `start` | 20 ms | 50 ms |
| Latence `cancel` bout en bout | 100 ms | 150 ms |
| Débit de partiels | 20/s | 1 / 50 ms |
| Mémoire sidecar | 500 Mo | 800 Mo |
| Perte de `done` sous charge | 0 | 0 |

## 9. Risques

| Risque | Mitigation |
|---|---|
| Refonte Rust régressive | Tests unitaires du dispatcher + intégration réelle |
| Interblocage writer/worker | File bornée, writer unique, tests de charge |
| Course sur `RunRegistry` | Accès verrouillé, `seq` par run |
| Persistance en double | `final` seul, idempotence par `runId` |
| Sidecar qui redémarre | Échec explicite de tous les `pending` |

## 10. Definition of Done

- [ ] Protocole `1.10.0` généré et vérifié.
- [ ] Sidecar concurrent, writer sérialisé, annulation effective.
- [ ] Rust non bloquant, notifications routées.
- [ ] Wrapper TS unique et filtré.
- [ ] Tests de charge et de latence consignés.
- [ ] La phase 08 peut brancher le store sans toucher au transport.
