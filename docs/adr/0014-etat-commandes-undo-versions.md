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

### Dispositions

- `PanelGrid` : trois fractions (`left`, `main`, `right`) dans des bornes, presets `analyse`, `pilotage`, `presentation`, `custom`.
- Persistance `localStorage` par projet (`sf-cockpit-layout:<projectId>`), validation au chargement, repli sur le preset par défaut.
- La disposition n'entre pas dans l'historique des hypothèses.

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

- Vitest + Testing Library + jsdom sont ajoutés en phase 08 et intégrés à `npm test`.
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
