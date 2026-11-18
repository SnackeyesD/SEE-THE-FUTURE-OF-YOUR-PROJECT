# IPC de flux — mesures de la phase 06

> Mesures du 2026-11-18 sur la machine de développement, protocole **1.10.0**.
> Commande reproductible : `npm run bench:ipc` → [`ipc.json`](ipc.json).
> Les chiffres sont ponctuels : ils servent à vérifier les ordres de grandeur des
> cibles, pas à comparer deux machines.

## 1. Conditions

| Élément | Valeur |
|---|---|
| Date | 2026-11-18 |
| Protocole | 1.10.0 |
| Sidecar | 0.1.0 |
| Python | 3.14.9 |
| Scénario | `packages/engine/examples/retail_depot.json`, horizon forcé à 12 mois |
| Répétitions `start` | 10 |
| Config « final long » | 120 000 runs, `batchSize` 512 |
| Config « flux » | 8 000 runs, `batchSize` 256 |
| Machine | Linux x86_64 (machine de développement) |

## 2. Résultats

### 2.1 Démarrage d'un calcul

| Mesure | Échantillons (ms) | Médiane | Max | Cible |
|---|---|---|---|---|
| Réponse `simulation.start` | 2,02 / 1,93 / 1,93 / 1,26 / 1,34 / 1,30 / 1,25 / 1,26 / 1,31 / 1,28 | **1,31 ms** | **2,02 ms** | 20 ms (plafond 50 ms) |

La réponse ne dépend pas de la durée du calcul : elle est écrite avant la mise
en file du job (`SimulationService.activate()`), donc le client connaît toujours
le `runId` avant le premier événement.

### 2.2 Concurrence

| Mesure | Résultat | Cible |
|---|---|---|
| `ping` pendant un `final` long | **1,23 ms** | répondre sans attendre la fin |
| `cancel` bout en bout (RPC + notification) | **3,15 ms** | 100 ms (plafond 150 ms) |
| Deux `start` successifs | 1er `simulation.cancelled` (`simulation_superseded`), 2e `simulation.done` | un seul run actif |
| `partial` après `done`/`cancelled` | **0** | 0 |
| `seq` strictement croissants | **oui** (1 → 5) | obligatoire |
| `done.seq` | **5** = dernier `seq` partiel | dernier `seq` émis |

### 2.3 Flux et taille

| Mesure | Résultat | Cible |
|---|---|---|
| Partiels émis | 5 (throttle 50 ms) | ≥ 20/s |
| Payload partiel max | **16 051 octets** (≈ 15,7 Kio) | ≤ 500 Ko |
| Message max | < 1 Mo | ≤ 1 Mo |
| `done` perdu sous charge | 0 | 0 |

### 2.4 Mémoire

| Élément | Valeur |
|---|---|
| RSS avant la série de runs | 66,6 Mo |
| RSS après la série | 98,8 Mo |
| Cible | ≤ 500 Mo |

## 3. Ce que ces mesures ne disent pas

- Le banc exerce le sidecar Python réel via stdio, mais **pas** le transport
  Rust : la latence `ping` pendant un `final` prouve que la boucle RPC n'est
  plus bloquée, pas que la commande Tauri est non bloquante. Ce point est
  couvert par les tests unitaires du dispatcher Rust et l'usage du handle
  cloné (aucun verrou global tenu pendant l'attente).
- La charge « 10 changements de paramètre en 2 s » est vérifiée par les tests
  (`test_new_start_supersedes_the_previous_run`) et la politique de supersede,
  pas par une mesure de fps UI.
- Les tailles de partiels dépendent du nombre d'hypothèses et de la taille des
  histogrammes du scénario. Le plafond de 500 Ko est vérifié à l'émission
  (`MAX_PARTIAL_BYTES`) ; un partiel trop gros est ignoré, jamais tronqué.
- Le RSS augmente avec les runs retenus (TTL 15 min, plafond 20 runs) ; il
  redescend après éviction, mais le banc ne mesure pas ce retour.

## 4. Lecture

Les trois cibles de la phase sont tenues avec une marge importante :
`start` ≈ 1,3 ms (cible 20 ms), `cancel` ≈ 3,2 ms (cible 100 ms), partiel
max ≈ 16 Ko (cible 500 Ko). Le gain principal n'est pas la vitesse brute mais
la **non-blocking** : un calcul long n'empêche plus `ping`, `health` ou
`project.list` de répondre, et l'annulation est effective en quelques
millisecondes.
