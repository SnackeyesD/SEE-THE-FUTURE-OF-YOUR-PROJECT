# Phase 10 — Temps & événements UI

> **Objectif** : piloter la simulation dans le temps et dans les imprévus : curseur de mois, distribution de l'état au mois choisi, frise d'événements éditable, catalogue, raccourcis et palette de commandes.

**Références** : `V3-COCKPIT.md` §6.1, §7 (I4, I5, I13), §3.3.
**Dépend de** : phase 09 (cockpit), phase 05 (moteur d'événements), phase 08 (commandes).
**Débloque** : 11 (objectif avec événements), 15 (démo).
**Profil** : intermédiaire UI (senior pour la frise et l'accessibilité) ; 5–6 jours.

**État au 2026-11-20** : **livrable**. Les constats de la revue
[`REVUE-PHASE-10.md`](REVUE-PHASE-10.md) sont traités, les tests dédiés sont
écrits et verts (desktop 155/155, engine 130/130, sidecar 48/48). Le protocole
passe en `1.11.0`. Les commits sont découpés sur `v3/cockpit` (voir §11).

---

## 1. Contexte

Le cockpit statique montre l'horizon complet. La V3 doit permettre de :

- lire l'état **mois par mois** (distribution, pas seulement une moyenne) ;
- ajouter un imprévu, le placer, régler sa durée et son intensité, et voir l'effet ;
- tout faire au clavier, sans dépendre du glisser-déposer.

## 2. Périmètre

**Inclus**

- Curseur de temps, lecture/pause, raccourcis.
- Histogramme de l'état au mois sélectionné (profit/trésorerie).
- Frise d'événements : ajout, déplacement, redimensionnement, suppression, activation.
- Catalogue d'événements issu du moteur, éditeur d'intensité et de probabilité.
- Palette de commandes (Ctrl+K).
- Accessibilité et alternatives clavier à la frise.
- Tests de géométrie, de commandes et d'intégration.

**Exclu**

- Recherche d'objectif (phase 11).
- Heatmap/tornado (phase 11).
- 3D (phase 14).

## 3. Livrables

- [x] `components/cockpit/TimeScrubber.tsx`, `MonthInspector.tsx`.
- [x] `components/cockpit/EventTimeline.tsx`, `EventCatalog.tsx`, `EventEditor.tsx`.
- [x] `components/CommandPalette.tsx` et `ShortcutsHelp.tsx`.
- [x] Schéma de distributions mensuelles côté moteur/protocole
      (`SimulationConfig.includeMonthlyHistograms`, protocole `1.11.0`).
- [x] Raccourcis documentés dans l'aide (`lib/shortcuts.ts` → `ShortcutsHelp`).
- [x] Tests dédiés phase 10 : géométrie, playback, raccourcis, éditeur, frise,
      focus des dialogues et parcours d'intégration.

## 4. Tâches détaillées

### Lot A — Distribution mensuelle

- [x] Le payload final fournit, par mois, les histogrammes profit et trésorerie
      (`MonthlyAverage.profitHistogram` / `cashHistogram`).
- [x] `SimulationConfig.includeMonthlyHistograms` (défaut `false`) demande **tous**
      les mois et prime sur `histogramMonth`.
  - Le sidecar force le flag à `true` uniquement quand `quality == "final"` ;
    les partiels n'envoient jamais d'histogramme mensuel.
  - Payload 36 mois × 2 métriques × 20 bins testé sous 200 Ko côté moteur et
    sidecar.
- [x] L'UI affiche la « distribution du dernier calcul final » avec la date
      (`RunState.computedAt`) et la graine ; elle n'invente jamais de distribution.
      Les anciens runs sans histogrammes affichent un message et un bouton de relance.

### Lot B — Curseur de temps

- [x] `TimeScrubber` : piste `input[type=range]` de 1 à horizon, ticks
      trimestriels cliquables, valeur « Mois N / horizon ».
- [x] Lecture/pause (`Espace` ou bouton) : 1 mois / 400 ms ; pause automatique
      sur `blur` et `visibilitychange` ; arrêt en fin d'horizon.
- [x] Flèches ←/→ : mois précédent/suivant ; `Home`/`End` : premier/dernier.
- [x] Le mois sélectionné met à jour **toutes** les vues temporelles :
      crosshair, inspecteur et probabilité de point mort de `KpiBar` (le mois
      courant est accepté même hors `[6, 12, 18, horizon]`).
- [x] **Aucun recalcul moteur** pour changer de mois : tout vient du résultat courant.
- [x] Si le mois dépasse l'horizon d'un nouveau résultat, il est borné **et**
      signalé (`cockpit-month-notice`).

### Lot C — Frise d'événements

- [x] Bloc `[start, start + duration - 1]` (durée inclusive, API 1-based).
- [x] Glisser le bloc : déplacement d'un mois entier (snap), aperçu local.
- [x] Poignées gauche/droite : durée minimale 1 mois, fenêtre bornée à l'horizon.
- [x] Pendant le drag : mise à jour **locale** (aucune simulation) ; au drop :
      une commande + un seul `runFinal` (invalidation automatique neutralisée).
- [x] Double-clic et menu contextuel : éditer, activer/désactiver, dupliquer,
      supprimer (chaque action est une commande annulable).
- [x] Couleur par type **et** libellé du catalogue (pas de couleur seule).
- [x] **Alternative clavier** : flèches déplacer, `Shift+←/→` durée,
      `Alt+←/→` début, `Entrée` éditer, `Suppr` supprimer, `Espace` activer.
- [x] Empilement vertical glouton si les événements se chevauchent.
- [x] Corrections de revue : `pointercancel` annule le glissement sans commit et
      le menu contextuel n'est plus rogné par la piste.

### Lot D — Catalogue et éditeur

- [x] Catalogue généré depuis `engine.EVENT_CATALOG` vers
      `packages/protocol/src/catalog.generated.ts` (`npm run catalog:generate`),
      vérifié par `catalog:check`. Aucune duplication en dur, aucune méthode IPC.
- [x] Ajout : place l'événement au mois sélectionné, durée par défaut 3 mois,
      probabilité 100 %, magnitude par défaut du catalogue.
- [x] `EventEditor` :
  - début et durée (champs numériques, aperçu de fenêtre) ;
  - probabilité 0–100 % ;
  - intensité selon la loi (min/mode/max, moyenne/écart-type, valeurs) ;
  - cible et mode affichés en clair, activé/désactivé ;
  - avertissement local si la fenêtre dépasse l'horizon.
- [x] L'aperçu d'intensité est un **paramètre**, pas un résultat de simulation.
- [x] Chaque modification passe par une commande (undo/redo).
- [x] Les erreurs de validation du sidecar restent affichées **dans** l'éditeur :
      celui-ci attend l'acceptation du run et ne se ferme pas sur un refus.

### Lot E — Palette et raccourcis

- [x] `Ctrl+K` / `Cmd+K` : palette avec recherche (actions, dispositions, mois,
      événements du catalogue, aide). Filtre insensible aux accents et à la casse.
- [x] Raccourcis : `Espace` lecture, `←/→` temps, `Home/End`, `F` plein écran,
      `1–8` vues, `Ctrl+Z/Y`, `Ctrl+S` enregistrer, `?` aide, `Échap` fermer.
- [x] Ne pas intercepter les raccourcis quand un champ de saisie a le focus :
      `isTextEntryTarget`, `isInteractiveTarget`, `ownsActivationKeys` et
      `data-hotkeys-scope` couvrent champs, curseurs, boutons et dialogues.
- [x] Aide contextuelle (`?`) listant les raccourcis (`ShortcutsHelp`).

### Lot F — Tests

Les tests existants ont été adaptés (`KpiBar` avec mois contrôlé,
`CockpitScreen` avec `onSaveScenario`, `App` avec `includeMonthlyHistograms`) et
les tests spécifiques phase 10 sont écrits :

- [x] Géométrie : mois ↔ pixel, clamp, drag au-delà des bornes
      (`events.test.ts`).
- [x] Clavier : déplacement, durée, suppression, annulation
      (`useCockpitHotkeys.test.tsx`, `useViewHotkeys.test.tsx`,
      `usePlayback.test.tsx`, scénario annulé/rétabli).
- [x] Éditeur : validation, erreur serveur, attente du sidecar
      (`EventEditor.test.tsx`).
- [x] Intégration : ajouter un événement → calcul final ; undo/redo restaure.
- [x] Distribution mensuelle : sélection d'un mois met à jour l'inspecteur sans
      nouvel appel IPC.
- [x] Accessibilité : rôles, focus, alternatives clavier
      (`useDialogFocus.test.tsx`, `TimeScrubber.test.tsx`,
      `EventTimeline.test.tsx`).

## 5. Contrats

```ts
type EventDraft = {
  id: string;
  type: EventType;
  startMonth: number;   // 1-based
  durationMonths: number;
  probability: number;
  magnitude: DistributionSpec;
  enabled: boolean;
};

type MonthDistribution = {
  month: number;
  profit: Histogram;
  cash: Histogram;
};
```

Invariants :

- La frise ne dépasse jamais l'horizon.
- Un événement désactivé reste visible mais grisé et n'est pas tiré par le moteur.
- Le mois sélectionné est indépendant du run ; il survit à un nouveau résultat si
  l'horizon le permet.
- Un drag ne déclenche pas plus d'un calcul par drop.

## 6. Pièges

- **Recalculer à chaque pixel de drag** : le drop seul déclenche.
- **Distribution mensuelle calculée dans l'UI** : interdite ; elle vient du moteur.
- **Histogrammes dans les partiels** : trop lourds ; final seulement.
- **Confondre mois 1-based et 0-based** : l'API est 1-based, l'interne 0-based.
- **Palette qui capture les flèches** : vérifier `event.target` (input, textarea, contenteditable).
- **Couleur seule** : toujours un libellé/icône.
- **Playback qui continue en arrière-plan** : pause sur `blur` et `visibilitychange`.

## 7. Critères d'acceptation

- [x] Le curseur de temps change l'état affiché sans recalcul.
- [x] L'histogramme du mois sélectionné est fourni par le moteur.
- [x] Un événement peut être ajouté, déplacé, redimensionné, édité, désactivé,
      supprimé, annulé.
- [x] L'effet d'un événement est visible sur le graphique après le calcul.
- [x] Tout est faisable au clavier : la frise oui, et les gardes globales
      (boutons, dialogues, `Ctrl+K`/`Ctrl+S`) sont corrigées.
- [x] Les raccourcis n'interfèrent pas avec la saisie.
- [x] Tests dédiés et `ui:check` verts.

## 8. Performance

- Changer de mois < 16 ms.
- Drag de frise : 60 i/s en local, un seul calcul au drop.
- Payload final avec histogrammes : < 200 Ko (testé).
- Partiels inchangés : < 50 Ko (sans histogrammes mensuels).

## 9. Risques

| Risque | Mitigation |
|---|---|
| Frise complexe/inaccessible | Alternative clavier, tests, drag simple |
| Payload trop gros | Histogrammes final seulement, bins limités |
| Événements incohérents | Validation moteur, messages clairs |
| Recalculs excessifs | Drag local, drop unique |
| Raccourcis conflictuels | Guard input, documentation |

## 10. Definition of Done

- [x] Temps, événements et palette livrés, corrections de revue incluses.
- [x] Distribution mensuelle fournie par le moteur.
- [x] Accessibilité clavier validée (tests et gardes).
- [x] Tests d'intégration draft/final verts.
- [x] Documentation des raccourcis et du catalogue généré (ADR 0017).

## 11. État d'implémentation au 2026-11-20

Branche `v3/cockpit`, partie de `d09ab21` (phase 09). La phase 10 est
**committée** par lots cohérents : protocole/moteur, catalogue, socle UI,
temps, frise/éditeur/palette, docs et tests.

### Livré

| Domaine | Fichiers / points clés |
|---|---|
| Protocole | `messages.schema.json` en `1.11.0`, champ `includeMonthlyHistograms`, `generated.ts` et `protocol_models.py` régénérés |
| Moteur | `SimulationConfig.include_monthly_histograms`, priorité sur `histogramMonth`, partiels sans histogrammes, tests de payload |
| Sidecar | `include_monthly_histograms = (quality == "final")`, tests « final tous les mois » / « partiels sans histogramme » |
| Catalogue | `packages/engine/scripts/export_events.py`, `packages/protocol/src/catalog.generated.ts`, scripts `catalog:generate` / `catalog:check` |
| Store | `RunState.computedAt`, `hydrateRun(result, computedAt)`, horodatage dans `applyFinal` |
| Temps | `TimeScrubber`, `MonthInspector`, `usePlayback`, sélection de mois partagée, notice de bornage |
| Événements | `events.ts` (géométrie pure), `EventTimeline`, `EventCatalog`, `EventEditor` |
| Palette / aide | `CommandPalette`, `ShortcutsHelp`, `lib/keyboard.ts`, `lib/shortcuts.ts`, `useCockpitHotkeys`, `useViewHotkeys` |
| Persistance | Bouton « Enregistrer le scénario », badge « modifications non enregistrées », `onSaveScenario`, garde `window.confirm` partagée par `navigate` et « Recharger », préservation de `events`/`seasonality` |
| Accessibilité | `useDialogFocus`, focus initial/piège de tabulation/restitution, `data-hotkeys-scope` |
| Styles | Blocs phase 10 dans `apps/desktop/src/styles.css`, utilitaires dans `packages/ui/src/primitives.css` |
| Tests | `events`, `TimeScrubber`, `usePlayback`, `useCockpitHotkeys`, `useViewHotkeys`, `EventEditor`, `EventTimeline`, `useDialogFocus`, intégration `CockpitScreen`, garde de rechargement `App` |
| Docs | cet état, ADR 0017, protocole `1.11.0` répercuté dans le plan et les phases 11/12 |

### Contrôles exécutés

| Contrôle | Résultat |
|---|---|
| `npm run protocol:check` | Vert |
| `npm run catalog:check` | Vert |
| `npm run typecheck` | Vert |
| `npm run lint` (dont `ui:check`) | Vert |
| `npm run test -w @see/desktop` | **155/155**, 25 fichiers |
| `pytest packages/engine/tests` | **130/130** |
| `pytest apps/desktop/src-tauri/sidecar/tests` | **48/48** après fiabilisation du harnais (`collect(..., timeout=30)` pour `project.create`) |

La revue du 2026-11-20 avait également validé le build web, le protocole, le
storage, les providers, l'agent core, les benchmarks, le sandbox et Rust. Ces
contrôles doivent être rejoués avant le commit final.

### Reste à faire avant merge

1. **Rejeu final** — relancer `npm run typecheck`, `npm run lint`,
   `npm run protocol:check`, `npm run catalog:check`, puis les suites engine,
   sidecar et desktop sur la branche prête à fusionner.
2. **Revue** — faire relire le diff par lot (protocole/moteur, catalogue, UI,
   docs) et vérifier le build web / Tauri avant merge.

Les points de revue (mois KPI, course de sauvegarde, rechargement, gardes
clavier, `pointercancel`, menu de frise, erreur sidecar, focus, bornage) sont
traités et couverts par les tests listés ci-dessus.

## 12. Réponse à la revue

La revue [`REVUE-PHASE-10.md`](REVUE-PHASE-10.md) est acceptée dans son
diagnostic. Décisions déjà actées :

- **Dirty sur le scénario seul** : la graine reste attachée au run et ne rend
  pas le scénario « dirty ». Persister la graine avec le scénario serait un
  changement de contrat, hors phase 10.
- **`includeMonthlyHistograms: true` dans le parcours Résultats** : conservé ;
  le run persisté est ainsi directement exploitable par le cockpit, sans
  recalcul ni fabrication de données côté React.
- **Nouveau `ScenarioRecord` à chaque sauvegarde** : conservé en phase 10 ;
  l'upsert/déduplication est une dette de la phase 13. Le provider reste donc
  clé sur `project.id` pour ne pas perdre l'historique des runs.
- **Harnais sidecar** : le `project.create` des tests utilise désormais un
  timeout de 30 s ; la suite complète est passée de 45–46/48 à **48/48**.
