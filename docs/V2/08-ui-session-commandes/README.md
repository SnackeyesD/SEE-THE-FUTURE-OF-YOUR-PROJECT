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

- [ ] `zustand` ajouté à `apps/desktop` (ADR 0014).
- [ ] `src/store/cockpitStore.ts` + slices (`session`, `runs`, `selection`, `layout`).
- [ ] `src/store/commands.ts` : commande, pile, coalescence.
- [ ] `src/hooks/useLiveSimulation.ts`.
- [ ] `src/components/layout/PanelGrid.tsx` + poignées + presets.
- [ ] Vitest + `@testing-library/react` + `jsdom` configurés.
- [ ] Tests du store, des commandes et du contrôleur.
- [ ] Documentation de ce qui est annulable et de ce qui ne l'est pas.

## 4. Tâches détaillées

### Lot A — Store

- [ ] Créer un store par application (pas un store global de module non testable) :
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
- [ ] Actions explicites : `setParam`, `setSeed`, `addEvent`, `updateEvent`, `removeEvent`, `startRun`, `applyPartial`, `applyFinal`, `cancelRun`, `pinRun`, `setSelection`, `setLayout`.
- [ ] Sélecteurs mémorisés pour le rendu ; éviter de renvoyer des objets recréés.
- [ ] Aucune mutation profonde directe : copie du scénario concerné.

### Lot B — Commandes et undo/redo

- [ ] Modèle :
  ```ts
  type Command = {
    label: string;
    undo: () => void;
    redo: () => void;
    coalesceKey?: string;
  };
  ```
- [ ] Toute action d'entrée passe par `dispatchCommand` :
  - paramètre, distribution, verrou, source ;
  - ajout/modification/suppression d'événement ;
  - seuil, graine, sélection d'axes ;
  - disposition (taille des panneaux, preset).
- [ ] Pile bornée à 100 ; `Ctrl+Z` / `Ctrl+Y` et boutons.
- [ ] **Coalescence** : pendant un glissement, ne pas empiler une commande par pixel. Capturer l'état au `pointerdown`, appliquer les changements en direct, pousser **une** commande au `pointerup` (ou après 400 ms d'inactivité).
- [ ] **Ce qui n'est pas annulable** : les résultats de simulation (partiels/final). Undo restaure les entrées et **invalide** le run courant, puis relance.
- [ ] Une commande qui modifie les entrées doit :
  - marquer le résultat courant comme `stale` ;
  - planifier un `draft` (ou un `final` selon le geste) ;
  - ne pas attendre la fin du calcul pour rendre la main.
- [ ] Ne pas persister la pile d'undo (session seulement).

### Lot C — Contrôleur live

- [ ] `useLiveSimulation` :
  - s'abonne au store et au flux IPC **une seule fois** ;
  - pendant un geste : `startSimulation({quality:"draft"})` au plus toutes les 50 ms ;
  - au relâchement ou après 400 ms d'inactivité : `startSimulation({quality:"final"})` ;
  - avant chaque `start`, `cancelSimulation(activeRunId)` si présent ;
  - ignore les événements dont `runId !== activeRunId` ou `seq <= lastSeq` ;
  - applique `partial` et `done` au store.
- [ ] Machine d'état simple : `idle → drafting → finalizing → idle | error`.
- [ ] En cas d'erreur : message lisible, conservation du dernier résultat valide, possibilité de relancer.
- [ ] Au démontage : `cancelSimulation` + `unlisten`.
- [ ] Ne jamais lancer un calcul si le scénario est invalide ; l'erreur vient du sidecar.

### Lot D — Dispositions

- [ ] `PanelGrid` : 3 zones (hypothèses, principal, secondaire) + barre KPI + frise, redimensionnables par poignées.
- [ ] Presets : `Analyse`, `Pilotage`, `Présentation` (fractions prédéfinies).
- [ ] Persistance `localStorage` clé `sf-cockpit-layout:<projectId>` ; validation des fractions au chargement.
- [ ] Plein écran par panneau, accessible au clavier.
- [ ] Pas de dockview : le besoin est de redimensionner et de choisir un preset, pas de réorganiser arbitrairement.
- [ ] Tests : les fractions restent dans `[min, max]`, le preset se restaure.

### Lot E — Tests UI

- [ ] Ajouter `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event` en devDependencies.
- [ ] Script `test` dans `apps/desktop/package.json` et intégration au `npm test` racine.
- [ ] Tests :
  - store : ajout/suppression d'événement, invalidation des runs ;
  - commandes : undo/redo, coalescence, pile bornée ;
  - contrôleur : draft → final, run périmé ignoré, cancel au démontage ;
  - layout : persistance et bornes.
- [ ] Shim IPC de test déterministe (pas d'appel Tauri réel).

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

- [ ] Un glissement de curseur produit un `draft` puis un `final`, sans calcul concurrent.
- [ ] Ctrl+Z/Ctrl+Y restaurent les entrées et relancent le calcul.
- [ ] Les résultats ne sont jamais dans la pile d'undo.
- [ ] Les dispositions survivent au redémarrage.
- [ ] Aucun événement périmé ne modifie l'état.
- [ ] Les tests UI tournent en CI (`npm test`).
- [ ] L'UI reste fluide (pas de re-render global) pendant un glissement.

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

- [ ] Store, commandes, contrôleur et layout livrés et testés.
- [ ] Vitest intégré au `npm test`.
- [ ] Règles « annulable / non annulable » documentées.
- [ ] La phase 09 peut se concentrer sur le rendu.
