# Phase 13 — Branches & comparaison

> **Objectif** : expérimenter sans peur. Dupliquer un scénario, comparer deux branches côte à côte, voir ce qui change dans les hypothèses, épingler des runs, créer et restaurer des versions nommées.

**Références** : `V3-COCKPIT.md` §5.1–5.2, §7 (I9, I12) ; plan maître C11.
**Dépend de** : phases 07 (modèle de données), 09 (cockpit, fantômes), 08 (commandes).
**Débloque** : 15 (dossier de pitch).
**Profil** : intermédiaire UI, revue senior sur la sémantique ; 4–5 jours.

---

## 1. Contexte

Le stockage V3 sait déjà représenter branches et versions (phase 07). Il manque l'expérience utilisateur :

- créer une branche à partir du scénario courant ;
- voir la différence d'hypothèses entre deux branches ;
- comparer deux résultats **avec la même graine** ;
- épingler un run comme référence (fantôme) ;
- nommer et restaurer une version.

## 2. Périmètre

**Inclus**

- Liste/arborescence de branches.
- Duplication, renommage, archivage.
- Diff d'hypothèses et d'événements.
- Comparaison côte à côte + deltas.
- Versions nommées : création, liste, restauration non destructive.
- Intégration undo/redo.
- Tests et états vides.

**Exclu**

- Synchronisation cloud.
- Fusion automatique de branches.
- Comparaison 3D (phase 14).

## 3. Livrables

- [x] `components/branches/BranchList.tsx`, `BranchDiff.tsx`, `ComparisonView.tsx`, `VersionList.tsx`.
- [x] `lib/scenarioDiff.ts` : aplatissement et diff purs.
- [x] Actions de store : créer/renommer/archiver une branche, créer/restaurer une version.
- [x] Écran ou panneau « Comparer ».
- [x] Tests unitaires du diff et tests de composants.

## 4. Tâches détaillées

### Lot A — Branches

- [x] Afficher les scénarios du projet : nom, libellé de branche, parent, date, graine du dernier run final.
- [x] « Dupliquer en branche » :
  - copie le scénario (hypothèses + événements) ;
  - `parent_id` = scénario source, `branch_label` saisi ;
  - commande annulable ;
  - ouvre la nouvelle branche dans le cockpit.
- [x] Renommer, archiver (soft delete) ; confirmation si des runs sont épinglés.
- [x] Ne pas afficher une hiérarchie complexe : une liste plate triée par date suffit en V3, avec un badge « branche de X ».
- [x] Limite : 20 branches actives par projet (message clair).

### Lot B — Diff d'hypothèses et d'événements

- [x] `flattenScenario(scenario)` : chemins feuilles (`assumptions.unit_price.value`, `events[ev1].magnitude.mode`, etc.).
- [x] Ignorer les champs volatils (`updatedAt`, ids de rendu).
- [x] `diffScenarios(a, b)` renvoie :
  ```ts
  type DiffEntry = {
    path: string;
    label: string;
    kind: "added" | "removed" | "changed" | "event-added" | "event-removed" | "event-changed";
    before?: unknown;
    after?: unknown;
  };
  ```
- [x] Affichage groupé : hypothèses, événements, graine.
- [x] Une valeur identique n'apparaît pas.
- [x] Unités et formatage métier dans l'affichage, pas dans le diff.

### Lot C — Comparaison côte à côte

- [x] Sélectionner deux runs `final` (ou branches → dernier run final).
- [x] **Vérifier la graine** : si différente, afficher un avertissement explicite et proposer de relancer avec la même graine ; ne pas comparer silencieusement.
- [x] Afficher :
  - [ ] FanChart superposé ou deux panneaux synchronisés (crosshair partagé) ;
  - tableau des métriques : P10/P50/P90 profit, point mort, financement, P(trésorerie<0) ;
  - delta signé et en % ;
  - diff des hypothèses ;
  - diff des événements.
- [x] Aucun calcul local : les deltas portent sur des valeurs du payload (soustraction autorisée, pas de simulation).
- [x] Export/partage : le dossier de pitch (phase 15) réutilise cette vue.

### Lot D — Versions nommées

- [x] « Enregistrer une version » : libellé + snapshot + graine.
- [ ] Liste des versions avec date, auteur (utilisateur local), métriques clés.
- [x] « Restaurer » : crée une **nouvelle branche** à partir du snapshot ; ne détruit jamais l'existant.
- [ ] Comparer une version à la branche courante via le même diff.
- [x] Suppression d'une version : confirmation, annulable ? (choisir : non annulable, confirmation explicite).
- [x] Une version n'est jamais modifiée.

### Lot E — Undo et cohérence

- [x] Création de branche, renommage, archivage, création de version : commandes annulables.
- [x] Restauration : commande annulable (supprime la branche créée).
- [x] Suppression de version : hors undo, confirmation.
- [x] Undo d'une duplication ne doit pas supprimer des runs épinglés rattachés : bloquer ou avertir.

### Lot F — Tests

- [x] `flattenScenario` : ordre stable, valeurs `null`, tableaux.
- [x] `diffScenarios` : ajout/suppression/modification, événements, aucun faux positif.
- [x] Duplication : parent, label, hypothèses identiques.
- [x] Comparaison : avertissement de graine différente.
- [x] Deltas : valeurs et signes corrects.
- [x] Restauration : nouvelle branche, scénario identique au snapshot.
- [x] Undo/redo sur les actions.
- [x] Limite de branches.

## 5. Contrats

```ts
type BranchRef = {
  scenarioId: string;
  name: string;
  branchLabel: string | null;
  parentId: string | null;
  updatedAt: string;
  lastFinalRunId: string | null;
  seed: number | null;
};
```

Règles :

- Une comparaison n'est valide que si les deux runs partagent la graine et la version du moteur ; sinon avertir.
- Une version est immuable.
- Une restauration crée toujours une branche.
- Le diff est une fonction pure, testable sans React.

## 6. Pièges

- **Comparer des graines différentes** : le résultat est du bruit, pas une différence de scénario.
- **Écraser le scénario courant** lors d'une restauration : non destructif obligatoire.
- **Diff bruyant** : ignorer les métadonnées, trier les chemins.
- **Branches illimitées** : plafonner et permettre l'archivage.
- **Undo qui casse des références** : vérifier les runs épinglés avant suppression.
- **Confondre branche et version** : la branche évolue, la version est un snapshot.

## 7. Critères d'acceptation

- [x] Dupliquer, renommer, archiver une branche, avec undo.
- [x] Diff lisible et fiable des hypothèses et événements.
- [x] Comparaison côte à côte avec avertissement de graine.
- [x] Versions nommées créées et restaurées sans destruction.
- [x] Deltas corrects, sans calcul de simulation local.
- [x] Tests et `ui:check` verts.

## 8. Performance

- Diff de 100 hypothèses + 20 événements < 5 ms.
- Comparaison de deux payloads < 16 ms de rendu.
- Liste de 20 branches < 100 ms.

## 9. Risques

| Risque | Mitigation |
|---|---|
| Sémantique floue | Règles écrites (branche vs version) |
| Comparaison invalide | Vérification de graine bloquante |
| Perte de données | Restauration non destructive, confirmations |
| UI complexe | Liste plate, diff groupé |

## 10. Definition of Done

- [x] Branches, diff, comparaison et versions livrés.
- [x] Undo cohérent.
- [x] Tests purs et composants verts.
- [x] Documentation utilisateur courte.

## 11. État d'implémentation (2026-11-23)

### Décisions effectives

- **Stockage** : migration `0007` ajoute `scenarios.archived_at` (soft delete) ; `LATEST_SCHEMA_VERSION` passe à 7. Aucune branche n'est jamais supprimée par l'archivage.
- **Protocole `1.14.0`** : douze méthodes `project.scenario.*`, `project.run.*` et `project.version.*`. Deux champs optionnels `scenarioId` ont aussi été ajoutés à `project.scenario.save` et `simulation.start` pour rattacher les écritures à la branche ouverte.
- **Passerelle Tauri** : une seule commande `project_call`, restreinte à une liste blanche (`PROJECT_CALL_METHODS`). Aucune méthode projet arbitraire n'est exposée au renderer.
- **Liste plate** : tri par date de création décroissante, badge « branche de X », graine du dernier run final, run le plus récent. Les archivées sont masquées par défaut et réaffichables.
- **Limite** : `MAX_ACTIVE_BRANCHES = 20`. La duplication et la restauration d'une version échouent avec un message explicite quand le plafond est atteint.
- **Diff pur** : `lib/scenarioDiff.ts` aplatit les en-têtes, hypothèses (clés triées) et événements (identifiants triés), ignore `schemaVersion` et ne renvoie que les feuilles réellement modifiées. Aucun calcul métier, aucun accès React.
- **Comparaison** : deux runs `final` sont chargés par `project.run.compare`. Une graine différente **ou** une version de moteur différente déclenche un avertissement explicite ; la comparaison n'est jamais présentée comme valide silencieusement. Les deltas sont des soustractions de valeurs du payload.
- **Branche ouverte** : `App` conserve un scénario override chargé par `project.scenario.get`. Le cockpit utilise cet identifiant (`scenarioId`) pour rattacher les runs et les enregistrements à la branche ; quitter le cockpit par la navigation principale efface l'override.
- **Undo/redo** : duplication, renommage, archivage, désarchivage, création de version et restauration de version passent par `CommandStack`. L'undo d'une duplication ou d'une restauration archive la branche créée (jamais de suppression) ; le redo la désarchive. L'undo d'une création de version supprime cette version précise ; le redo en recrée une.
- **Versions** : un snapshot fige le scénario, la graine et la version de moteur du dernier run. La restauration crée toujours une nouvelle branche et ne touche pas l'existant. La suppression reste explicite, confirmée et hors historique.
- **Écran** : nouvel onglet de navigation « Branches », trois sous-onglets `Branches & diff`, `Comparer`, `Versions`, états vides et erreurs lisibles.

### Écarts assumés

- **Relance automatique** : en cas de graines différentes, l'application avertit et explique le bruit, mais ne relance pas les deux branches avec une graine commune. La relance reste manuelle dans le cockpit, faute d'orchestrateur multi-branches.
- **Dataviz de comparaison** : le tableau de métriques et les deltas sont livrés ; le FanChart superposé ou les deux panneaux à crosshair partagé restent à faire (phase 14 pour la vue 3D, ensuite pour la comparaison graphique).
- **Versions** : la liste n'affiche ni auteur (mono-utilisateur local en V3) ni métriques clés, et la comparaison version ↔ branche via le même diff n'est pas encore exposée. Le snapshot contient toutes les données nécessaires.
- **Graine dans le diff** : la graine est affichée dans la liste des branches et dans la comparaison, pas comme entrée du diff d'hypothèses (elle ne fait pas partie du scénario sauvegardé).
- **Fusion de branches** : hors périmètre V3, aucune fusion automatique ni manuelle.
- **Suppression de version** : non annulable par choix produit ; l'undo d'une création de version est autorisé, la suppression confirmée reste définitive.

### Fichiers

- Stockage : `packages/storage/see_storage/migrations/__init__.py`, `models.py`, `repositories.py`, `cloning.py`.
- Protocole : `packages/protocol/schema/messages.schema.json`, `packages/protocol/src/generated.ts`, `sidecar/protocol_models.py`.
- Sidecar : `project_service.py`, `simulation_service.py`, `rpc.py`, `tests/test_branch_service.py`, `tests/test_rpc.py`.
- Tauri : `apps/desktop/src-tauri/src/lib.rs` (`project_call`).
- Desktop : `lib/ipc.ts`, `lib/scenarioDiff.ts` (+ tests), `components/branches/*`, `screens/BranchesScreen.tsx` (+ tests), `store/cockpitStore.ts`, `store/CockpitProvider.tsx`, `hooks/useLiveSimulation.ts`, `screens/CockpitScreen.tsx`, `App.tsx`, `styles.css`.
