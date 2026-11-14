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

- [ ] `components/branches/BranchList.tsx`, `BranchDiff.tsx`, `ComparisonView.tsx`, `VersionList.tsx`.
- [ ] `lib/scenarioDiff.ts` : aplatissement et diff purs.
- [ ] Actions de store : créer/renommer/archiver une branche, créer/restaurer une version.
- [ ] Écran ou panneau « Comparer ».
- [ ] Tests unitaires du diff et tests de composants.

## 4. Tâches détaillées

### Lot A — Branches

- [ ] Afficher les scénarios du projet : nom, libellé de branche, parent, date, graine du dernier run final.
- [ ] « Dupliquer en branche » :
  - copie le scénario (hypothèses + événements) ;
  - `parent_id` = scénario source, `branch_label` saisi ;
  - commande annulable ;
  - ouvre la nouvelle branche dans le cockpit.
- [ ] Renommer, archiver (soft delete) ; confirmation si des runs sont épinglés.
- [ ] Ne pas afficher une hiérarchie complexe : une liste plate triée par date suffit en V3, avec un badge « branche de X ».
- [ ] Limite : 20 branches actives par projet (message clair).

### Lot B — Diff d'hypothèses et d'événements

- [ ] `flattenScenario(scenario)` : chemins feuilles (`assumptions.unit_price.value`, `events[ev1].magnitude.mode`, etc.).
- [ ] Ignorer les champs volatils (`updatedAt`, ids de rendu).
- [ ] `diffScenarios(a, b)` renvoie :
  ```ts
  type DiffEntry = {
    path: string;
    label: string;
    kind: "added" | "removed" | "changed" | "event-added" | "event-removed" | "event-changed";
    before?: unknown;
    after?: unknown;
  };
  ```
- [ ] Affichage groupé : hypothèses, événements, graine.
- [ ] Une valeur identique n'apparaît pas.
- [ ] Unités et formatage métier dans l'affichage, pas dans le diff.

### Lot C — Comparaison côte à côte

- [ ] Sélectionner deux runs `final` (ou branches → dernier run final).
- [ ] **Vérifier la graine** : si différente, afficher un avertissement explicite et proposer de relancer avec la même graine ; ne pas comparer silencieusement.
- [ ] Afficher :
  - FanChart superposé ou deux panneaux synchronisés (crosshair partagé) ;
  - tableau des métriques : P10/P50/P90 profit, point mort, financement, P(trésorerie<0) ;
  - delta signé et en % ;
  - diff des hypothèses ;
  - diff des événements.
- [ ] Aucun calcul local : les deltas portent sur des valeurs du payload (soustraction autorisée, pas de simulation).
- [ ] Export/partage : le dossier de pitch (phase 15) réutilise cette vue.

### Lot D — Versions nommées

- [ ] « Enregistrer une version » : libellé + snapshot + graine.
- [ ] Liste des versions avec date, auteur (utilisateur local), métriques clés.
- [ ] « Restaurer » : crée une **nouvelle branche** à partir du snapshot ; ne détruit jamais l'existant.
- [ ] Comparer une version à la branche courante via le même diff.
- [ ] Suppression d'une version : confirmation, annulable ? (choisir : non annulable, confirmation explicite).
- [ ] Une version n'est jamais modifiée.

### Lot E — Undo et cohérence

- [ ] Création de branche, renommage, archivage, création de version : commandes annulables.
- [ ] Restauration : commande annulable (supprime la branche créée).
- [ ] Suppression de version : hors undo, confirmation.
- [ ] Undo d'une duplication ne doit pas supprimer des runs épinglés rattachés : bloquer ou avertir.

### Lot F — Tests

- [ ] `flattenScenario` : ordre stable, valeurs `null`, tableaux.
- [ ] `diffScenarios` : ajout/suppression/modification, événements, aucun faux positif.
- [ ] Duplication : parent, label, hypothèses identiques.
- [ ] Comparaison : avertissement de graine différente.
- [ ] Deltas : valeurs et signes corrects.
- [ ] Restauration : nouvelle branche, scénario identique au snapshot.
- [ ] Undo/redo sur les actions.
- [ ] Limite de branches.

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

- [ ] Dupliquer, renommer, archiver une branche, avec undo.
- [ ] Diff lisible et fiable des hypothèses et événements.
- [ ] Comparaison côte à côte avec avertissement de graine.
- [ ] Versions nommées créées et restaurées sans destruction.
- [ ] Deltas corrects, sans calcul de simulation local.
- [ ] Tests et `ui:check` verts.

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

- [ ] Branches, diff, comparaison et versions livrés.
- [ ] Undo cohérent.
- [ ] Tests purs et composants verts.
- [ ] Documentation utilisateur courte.
