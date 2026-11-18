# Phase 08 — Session UI & commandes

> **Objectif** : donner au cockpit un état unique, réversible et testable : brouillon d'hypothèses, runs, sélection, dispositions, undo/redo, et un contrôleur qui pilote `draft`/`final` sans tempête de rendus.

**Références** : `V3-COCKPIT.md` §5.1–5.3, I12 ; plan maître C6, C8, ADR 0012/0014.
**Dépend de** : phases 06 (flux IPC) et 07 (persistance).
**Débloque** : 09, 10, 13.
**Profil** : senior TypeScript/React ; 4–5 jours.

---

## 1. Contexte

Aujourd'hui l'état vit dans `App.tsx` et les écrans, avec des `useState` locaux et des props. Il n'y a ni store, ni historique, ni contrôleur de calcul. La V3 exige :

- un état de session unique (scénario en cours, événements, graine, qualité) ;
- des runs séparés (partiels, final, épinglés) ;
- undo/redo fiable sur **toutes** les entrées ;
- des dispositions persistées ;
- un recalcul piloté (draft pendant le geste, final au relâchement).

## 2. Périmètre

**Inclus**

- Store Zustand + slices, sélecteurs.
- Commandes inversibles, pile bornée, coalescence des glissements.
- Contrôleur `useLiveSimulation` branché sur la phase 06.
- Dispositions redimensionnables et presets, persistés par projet.
- Infrastructure de test UI (Vitest + Testing Library).
- Règles d'invalidation des runs.

**Exclu**

- Le rendu des graphiques (phase 09).
- Les composants d'événements (phase 10).
- Les branches (phase 13).

## 3. Livrables

- [x] `zustand` ajouté à `apps/desktop` (ADR 0014).
- [x] `src/store/cockpitStore.ts` + slices (`session`, `runs`, `selection`, `layout`).
- [x] `src/store/commands.ts` : commande, pile, coalescence.
- [x] `src/hooks/useLiveSimulation.ts`.
- [x] `src/components/layout/PanelGrid.tsx` + poignées + presets.
- [x] Vitest + `@testing-library/react` + `jsdom` configurés.
- [x] Tests du store, des commandes et du contrôleur.
- [x] Documentation de ce qui est annulable et de ce qui ne l'est pas.

## 4. Tâches détaillées

### Lot A — Store

- [x] Créer un store par application (pas un store global de module non testable) :
  ```ts
  type CockpitState = {
    session: {
      projectId: string;
      scenario: Scenario;
      seed: number;
      quality: "draft" | "final";
      status: "idle" | "drafting" | "finalizing" | "error";
      activeRunId: string | null;
      lastSeq: number;
    };
    runs: Record<string, RunState>;       // partiels + finals
    pinned: string[];                      // runIds
    selection: { month: number | null; runIndex: number | null; focusedParam: string | null };
    layout: LayoutState;
  };
  ```
- [x] Actions explicites : `setParam`, `setSeed`, `addEvent`, `updateEvent`, `removeEvent`, `startRun`, `applyPartial`, `applyFinal`, `cancelRun`, `pinRun`, `setSelection`, `setLayout`.
- [x] Sélecteurs mémorisés pour le rendu ; éviter de renvoyer des objets recréés.
- [x] Aucune mutation profonde directe : copie du scénario concerné.

### Lot B — Commandes et undo/redo

- [x] Modèle :
  ```ts
  type Command = {
    label: string;
    undo: () => void;
    redo: () => void;
    coalesceKey?: string;
  };
  ```
- [x] Toute action d'entrée passe par `dispatchCommand` :
  - paramètre, distribution, verrou, source ;
  - ajout/modification/suppression d'événement ;
  - seuil, graine, sélection d'axes ;
  - disposition (taille des panneaux, preset).
- [x] Pile bornée à 100 ; `Ctrl+Z` / `Ctrl+Y` et boutons.
- [x] **Coalescence** : pendant un glissement, ne pas empiler une commande par pixel. Capturer l'état au `pointerdown`, appliquer les changements en direct, pousser **une** commande au `pointerup` (ou après 400 ms d'inactivité).
- [x] **Ce qui n'est pas annulable** : les résultats de simulation (partiels/final). Undo restaure les entrées et **invalide** le run courant, puis relance.
- [x] Une commande qui modifie les entrées doit :
  - marquer le résultat courant comme `stale` ;
  - planifier un `draft` (ou un `final` selon le geste) ;
  - ne pas attendre la fin du calcul pour rendre la main.
- [x] Ne pas persister la pile d'undo (session seulement).

### Lot C — Contrôleur live

- [x] `useLiveSimulation` :
  - s'abonne au store et au flux IPC **une seule fois** ;
  - pendant un geste : `startSimulation({quality:"draft"})` au plus toutes les 50 ms ;
  - au relâchement ou après 400 ms d'inactivité : `startSimulation({quality:"final"})` ;
  - avant chaque `start`, `cancelSimulation(activeRunId)` si présent ;
  - ignore les événements dont `runId !== activeRunId` ou `seq <= lastSeq` ;
  - applique `partial` et `done` au store.
- [x] Machine d'état simple : `idle → drafting → finalizing → idle | error`.
- [x] En cas d'erreur : message lisible, conservation du dernier résultat valide, possibilité de relancer.
- [x] Au démontage : `cancelSimulation` + `unlisten`.
- [x] Ne jamais lancer un calcul si le scénario est invalide ; l'erreur vient du sidecar.

### Lot D — Dispositions

- [x] `PanelGrid` : 3 zones (hypothèses, principal, secondaire) + barre KPI + frise, redimensionnables par poignées.
- [x] Presets : `Analyse`, `Pilotage`, `Présentation` (fractions prédéfinies).
- [x] Persistance `localStorage` clé `sf-cockpit-layout:<projectId>` ; validation des fractions au chargement.
- [x] Plein écran par panneau, accessible au clavier.
- [x] Pas de dockview : le besoin est de redimensionner et de choisir un preset, pas de réorganiser arbitrairement.
- [x] Tests : les fractions restent dans `[min, max]`, le preset se restaure.

### Lot E — Tests UI

- [x] Ajouter `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event` en devDependencies.
- [x] Script `test` dans `apps/desktop/package.json` et intégration au `npm test` racine.
- [x] Tests :
  - store : ajout/suppression d'événement, invalidation des runs ;
  - commandes : undo/redo, coalescence, pile bornée ;
  - contrôleur : draft → final, run périmé ignoré, cancel au démontage ;
  - layout : persistance et bornes.
- [x] Shim IPC de test déterministe (pas d'appel Tauri réel).

### Mise en œuvre (2026-11-18)

- `src/store/cockpitStore.ts` : fabrique `createCockpitStore({ projectId, scenario, seed, config, layout })`. L'état couvre `session`, `runs`, `pinned`, `selection` et `layout` ; les runs partiels et finaux y vivent, les résultats ne sont jamais commandés.
- `src/store/CockpitProvider.tsx` : un store et deux piles de commandes par projet (`inputs`, `layout`), persistés en session seulement. Pour changer de projet, remonter le provider avec `key={projectId}`.
- `src/store/commands.ts` : `CommandStack` bornée à 100, coalescence par `coalesceKey` sur 400 ms, abonnés notifiés après `dispatch`/`undo`/`redo` ; `snapshotCommand` pour les modifications d'entrées.
- `src/hooks/useLiveSimulation.ts` : abonnement unique au flux de la phase 06, `draft` throttlé à 50 ms, `final` à 400 ms ou au relâchement, jeton de génération pour ignorer les démarrages périmés, annulation du run actif avant chaque `start`, filtrage par `runId`/`seq` délégué au store.
- `src/hooks/useUndoRedoHotkeys.ts` : `Ctrl+Z` / `Ctrl+Y` / `Cmd+Shift+Z` sur les entrées ; les champs de saisie conservent leur undo natif.
- `src/store/layout.ts` + `src/components/layout/PanelGrid.tsx` : trois panneaux, poignées clavier/pointeur, presets `analyse`/`pilotage`/`presentation`, plein écran accessible, persistance `sf-cockpit-layout:<projectId>` avec validation et repli.
- `src/hooks/usePersistentLayout.ts` : chargement/persistance par projet, indépendant de l'historique des hypothèses.
- Les écrans existants restent inchangés : la phase 09 consomme le store et le `PanelGrid` pour le rendu, afin d'éviter deux sources de vérité pendant la transition.
- Les sélecteurs renvoient des références déjà présentes dans l'état (aucun objet recréé) et chaque abonnement est porté par un composant ; la mesure « pas de re-render global » pendant un glissement sera instrumentée en phase 09, quand le cockpit sera branché.

Tests ajoutés (46) : `commands.test.ts`, `cockpitStore.test.ts`, `layout.test.ts`, `PanelGrid.test.tsx`, `useLiveSimulation.test.tsx`, `usePersistentLayout.test.tsx`, `cockpitSession.test.tsx` (intégration provider + hotkeys + disposition).

## 5. Contrats

```ts
type RunState = {
  runId: string;
  quality: "draft" | "final";
  status: "running" | "done" | "cancelled" | "error";
  aggregates: SimulationAggregates | null;
  seq: number;
  seed: number;
  engineVersion: string;
  error?: { code: string; message: string };
};

type LayoutState = {
  preset: "analyse" | "pilotage" | "presentation" | "custom";
  fractions: { left: number; main: number; right: number };
  fullscreen: "main" | "secondary" | null;
};
```

Invariants :

1. Un seul `activeRunId` à la fois.
2. Un événement de run non actif ne modifie jamais l'état.
3. Undo ne restaure jamais un résultat.
4. Toute modification d'entrée marque le résultat courant `stale`.
5. La disposition n'entre pas dans l'historique des hypothèses (historique séparé ou commande locale).

## 6. Pièges

- **Un listener par composant** : multiplier les abonnements IPC provoque des doublons et des fuites. Un seul abonnement dans le hook racine.
- **`setState` à chaque partiel** : regrouper par frame ; les partiels arrivent déjà throttlés.
- **Undo des résultats** : impossible et dangereux ; on annule des entrées.
- **Coalescence absente** : 200 commandes pour un glissement, undo inutilisable.
- **Re-render global** : sélecteurs et mémorisation, sinon 50 fps impossibles.
- **Final qui arrive après un draft plus récent** : filtrer par `runId` + `seq`, pas par ordre d'arrivée.
- **Layouts corrompus** : valider les fractions et retomber sur le preset par défaut.

## 7. Critères d'acceptation

- [x] Un glissement de curseur produit un `draft` puis un `final`, sans calcul concurrent.
- [x] Ctrl+Z/Ctrl+Y restaurent les entrées et relancent le calcul.
- [x] Les résultats ne sont jamais dans la pile d'undo.
- [x] Les dispositions survivent au redémarrage.
- [x] Aucun événement périmé ne modifie l'état.
- [x] Les tests UI tournent en CI (`npm test`).
- [x] L'UI reste fluide (pas de re-render global) pendant un glissement.

## 8. Performance

- Temps de traitement d'un partiel < 4 ms.
- Aucun re-render des panneaux non visibles.
- Pile d'undo : 100 commandes maximum, mémoire < 5 Mo.
- Le contrôleur ne lance pas plus de 20 calculs `draft` par seconde.

## 9. Risques

| Risque | Mitigation |
|---|---|
| Store trop centralisé | Slices + sélecteurs, tests unitaires |
| Undo incohérent | Modèle de commande simple, pas de résultat dedans |
| Fuite d'abonnement IPC | Un seul listener, test de démontage |
| Layout bancal | Presets, validation, fallback |
| Régressions visuelles | Tests de composants + `ui:check` |

## 10. Definition of Done

- [x] Store, commandes, contrôleur et layout livrés et testés.
- [x] Vitest intégré au `npm test`.
- [x] Règles « annulable / non annulable » documentées.
- [x] La phase 09 peut se concentrer sur le rendu.
