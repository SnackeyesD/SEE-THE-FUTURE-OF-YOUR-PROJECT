# ADR 0014 — État, commandes inversibles, versions et branches

- **Statut** : accepté
- **Date** : 2026-11-14
- **Contexte** : phase 01, s'applique en phases 07–08 et 13

## Décision

### État UI

- **Zustand** pour l'état de session du cockpit, avec des slices : `session`, `runs`, `selection`, `layout`.
- Un store par application (créé dans un provider/test), pas un singleton de module non testable.
- Sélecteurs mémorisés ; aucune mutation profonde directe ; pas de re-render global à chaque partiel.

### Commandes et undo

- Toute modification d'entrée passe par une **commande inversible** :
  ```ts
  type Command = {
    label: string;
    undo: () => void;
    redo: () => void;
    coalesceKey?: string;
  };
  ```
- Pile bornée à 100 commandes, non persistée (session seulement).
- **Coalescence** : un glissement capture l'état au `pointerdown`, applique en direct, et pousse **une** commande au `pointerup` (ou après 400 ms d'inactivité).
- Sont annulables : hypothèses, distributions, verrous, sources, événements, seuil, graine, sélection d'axes, disposition (historique local).
- **Ne sont pas annulables** : les résultats de simulation (partiels et finaux). Undo restaure les entrées, marque le résultat courant `stale` et relance.
- Une commande qui modifie les entrées ne doit jamais restaurer un résultat.

### Versions et branches

- **Branche** : scénario avec `parent_id` et `branch_label` ; elle évolue.
- **Version nommée** : snapshot **immuable** (scénario + graine + version moteur) dans `scenario_versions`.
- **Restaurer une version** crée toujours une **nouvelle branche** ; aucune destruction.
- Une comparaison exige la **même graine** et la même version de moteur ; sinon l'UI avertit explicitement.
- Maximum 20 branches actives par projet (archivage au-delà).
- Les résultats sont épinglables (`pinned=1`) ; un run épinglé n'est jamais purgé.
- Sémantique persistée par la migration `0006` (phase 07).

### Mise en œuvre phase 07

- `scenarios.parent_id` référence la branche source (`ON DELETE SET NULL`) ;
  `scenarios.branch_label` porte le nom affiché ; `scenarios.version` est un compteur
  d'édition structurelle (changement de `scenario` ou de `model`).
- `scenario_versions` stocke un snapshot immuable (`scenario_json`, `seed`,
  `engine_version`). Supprimer un scénario laisse ses versions intactes.
- `simulation_runs` porte `quality` (`final` seulement en base), `scenario_version_id`,
  `pinned` et `status` (`complete`, `failed`, `cancelled`).
- `RunRepository.prune(keep_last=200)` conserve les 200 runs les plus récents, puis ne
  supprime jamais un run épinglé ou lié à une version. `ProjectStore.prune_all()` applique
  cette politique à tous les projets ; le sidecar l'exécute au premier accès au store.
- Un résultat sérialisé de plus de `MAX_INLINE_RESULT_BYTES` (15 MiB) est externalisé dans
  `results/<projectId>/<runId>.json.gz`.
- Les archives `.simproj` passent en `schemaVersion = 6` ; les archives v5 sont migrées à
  l'import. Les champs et commandes IPC correspondants sont exposés en phase 13, pas en
  phase 07.

### Dispositions

- `PanelGrid` : trois fractions (`left`, `main`, `right`) dans des bornes, presets `analyse`, `pilotage`, `presentation`, `custom`.
- Persistance `localStorage` par projet (`sf-cockpit-layout:<projectId>`), validation au chargement, repli sur le preset par défaut.
- La disposition n'entre pas dans l'historique des hypothèses.

### Mise en œuvre phase 08

- **Zustand 5.1** (`createStore` vanilla) et non le binding React global : la fabrique
  `createCockpitStore({ projectId, scenario, seed, config, layout })` rend chaque test
  indépendant. `CockpitProvider` crée un store par projet ; changer de projet remonte le
  provider avec `key={projectId}`.
- Slices effectives : `session` (scénario, graine, config, qualité, statut, run actif),
  `runs` (partiels, finaux, statut, `seq`, `stale`), `pinned`, `selection`, `layout`.
  Les sélecteurs (`selectActiveRun`, `selectPinnedRuns`, `selectRun`) sont des fonctions
  pures utilisables via `useCockpit(store, selector)`.
- **Invariant résultats** : aucun résultat n'entre dans une commande. Une modification
  d'entrée marque les runs terminés non épinglés comme `stale` (`staleRuns`) ; un run
  épinglé n'est jamais invalidé.
- **Deux `CommandStack` distinctes** (`inputs`, `layout`) créées par le provider : le
  layout a son propre historique local et ne consomme pas une entrée d'undo des
  hypothèses. Les deux sont bornées à 100 et non persistées.
- **Coalescence** par `coalesceKey` sur 400 ms (`now` injectable pour les tests) : la
  commande fusionnée conserve le `before` de la première occurrence et le `redo` de la
  dernière. Un `dispatch` vide la pile de redo ; `undo`/`redo` remettent le compteur de
  coalescence à zéro.
- **Contrôleur** `useLiveSimulation` :
  - un seul abonnement à `onSimulationEvent` par provider, filtré par `runId` actif ;
  - `draft` throttlé à 50 ms, `final` différé de 400 ms ou déclenché au relâchement ;
  - `beginGesture()` suspend tout calcul (y compris le final), `endGesture()` lance
    immédiatement le `final` ;
  - avant chaque `start`, le run actif est annulé ; un jeton de génération empêche un
    `start` périmé d'écraser l'état (le run accepté est alors annulé côté sidecar) ;
  - les `seq` décroissants et les événements d'un run non actif sont ignorés par le
    store, pas par le hook ; le démontage annule le run actif et se désabonne.
- **Hotkeys** : `Ctrl+Z` / `Ctrl+Y` / `Cmd+Shift+Z` sur `window`, ignorées dans
  `INPUT`, `TEXTAREA`, `SELECT` et `contentEditable` pour préserver l'undo natif des
  champs. Toute commande (dispatch, undo, redo) notifie `onInputsChanged`, que l'écran
  branche sur `invalidate()`.
- **Disposition** : bornes `[0.15, 0.7]`, somme à `1 ± 0.01`, `clampFraction` réserve
  toujours la fraction minimale du panneau principal. Un preset stocké réimpose ses
  fractions ; seul `custom` conserve des fractions libres. `PanelGrid` expose des
  poignées `separator` clavier (flèches, `Shift` pour un pas rapide) et pointeur, ainsi
  qu'un plein écran `main`/`secondary` accessible.
- Les écrans existants (`App.tsx`, `SimulationScreen`, `ResultsScreen`) restent
  inchangés : la phase 09 branchera le store et le `PanelGrid` sur le rendu pour éviter
  deux sources de vérité pendant la transition.
- Le protocole IPC n'évolue pas (toujours `1.10.0`) : la phase 08 consomme les messages
  `simulation.*` de la phase 06.

## Contexte et raisons

- L'état actuel est dispersé dans `App.tsx` (`useState` locaux, `App.tsx:147-164`) et passé par props ; il n'y a ni historique ni contrôleur de calcul.
- Les résultats ne sont pas des entrées : les rendre annulables créerait des incohérences (un résultat restauré ne correspondrait plus au scénario).
- Les branches et versions n'existent pas en base (`scenarios` plat, `simulation_runs` sans qualité) : il faut les définir avant l'UI (phase 13).
- Le docking libre n'est pas nécessaire (ADR 0012) ; des fractions et des presets couvrent le besoin.

## Alternatives

- **Redux Toolkit** : plus de boilerplate pour un état local à l'application.
- **Jotai/Recoil** : atomique, moins adapté à un historique de commandes centralisé.
- **useReducer seul** : possible, mais le partage entre panneaux et le undo/redo deviennent vite manuels.
- **Undo par snapshots complets du scénario** : simple mais coûteux en mémoire et peu lisible ; les commandes inverses sont préférées.
- **Docking (dockview)** : rejeté (ADR 0012).

## Conséquences

- Vitest + Testing Library + jsdom ont été introduits dès le durcissement de la phase 03 et sont intégrés à `npm test` ; Playwright reste prévu en phase 16.
- Le store expose des actions explicites ; aucun composant ne parle directement au transport IPC.
- `useLiveSimulation` : un seul abonnement, `draft` throttlé à 50 ms pendant le geste, `final` au relâchement ou après 400 ms, annulation du run actif avant chaque `start`.
- Un événement de run non actif ou avec `seq <= lastSeq` est ignoré.
- Les tests couvrent : coalescence, pile bornée, invalidation, restauration de version, disposition corrompue.
- La migration 0006 doit préserver les bases v5 et les archives `.simproj` v5.

## Vérification

- Ctrl+Z/Ctrl+Y restaurent les entrées et relancent ; les résultats ne sont jamais dans la pile.
- Un glissement produit une seule commande et un seul `final`.
- Les dispositions survivent au redémarrage et retombent sur un preset si elles sont invalides.
- Une restauration de version crée une branche et laisse l'ancienne intacte.
- Une comparaison avec graines différentes est signalée, jamais silencieuse.
