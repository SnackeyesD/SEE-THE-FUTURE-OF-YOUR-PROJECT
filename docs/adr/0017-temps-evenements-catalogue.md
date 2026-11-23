# ADR 0017 — Temps, événements, catalogue et raccourcis du cockpit

- **Statut** : accepté
- **Date** : 2026-11-20
- **Contexte** : phase 10, s'appuie sur les ADR 0014 et 0015

## Décision

### Distribution mensuelle fournie par le moteur

- Le protocole passe en `1.11.0` avec `SimulationConfig.includeMonthlyHistograms`
  (défaut `false`).
- Quand le flag est vrai, **tous** les mois du payload final portent
  `profitHistogram` et `cashHistogram` ; le flag prime sur
  `histogramMonth`, qui reste accepté pour les clients existants.
- Le sidecar force `include_monthly_histograms = (quality == "final")`. Les
  partiels n'envoient **jamais** d'histogramme mensuel : le payload reste sous
  les budgets de la phase 06.
- React n'agrège ni ne recalcule aucune distribution : `MonthInspector` lit les
  bins du run final. Un run antérieur sans histogrammes affiche un message et
  propose de relancer, il n'extrapole pas.

### Catalogue d'événements généré

- `packages/engine/EVENT_CATALOG` est la source unique. Un script Python
  (`packages/engine/scripts/export_events.py`) produit
  `packages/protocol/src/catalog.generated.ts`.
- `npm run catalog:generate` écrit le fichier ; `npm run catalog:check` échoue
  si le fichier versionné diverge. Le contrôle tourne en CI dans le job Python,
  qui dispose déjà de `uv`.
- Aucune méthode IPC `event.catalog` : le catalogue est statique, typé et
  partagé par l'éditeur, la palette et la frise. Aucune copie en dur dans
  l'UI.

### Temps et sélection de mois

- Le mois vit dans le store (`selection.month`), pas dans un état local de
  composant. Changer de mois ne déclenche **aucun** appel moteur.
- `KpiBar` accepte un mois arbitraire et l'ajoute à ses options : la
  probabilité de point mort affichée est toujours celle du mois inspecté, même
  hors de la liste `6/12/18/horizon`.
- Le mois survit à un nouveau résultat tant que l'horizon le permet. S'il est
  ramené dans les bornes, l'écran l'annonce explicitement
  (`cockpit-month-notice`) au lieu de le corriger en silence.

### Frise d'événements

- La géométrie (clamp, déplacement, redimensionnement, empilement, conversion
  mois ↔ pixel) est extraite dans `events.ts`, pure et testée sans DOM.
- Pendant un glissement, seul un aperçu local est mis à jour. Au relâchement,
  une **seule** commande est poussée et un **seul** `runFinal` est lancé ;
  l'invalidation automatique est neutralisée le temps de la commande.
- `pointercancel` annule le glissement sans commit (tactile, perte de capture).
- Les durées sont inclusives et les API moteur 1-based : `{ startMonth: 3,
  durationMonths: 2 }` couvre les mois 3 et 4.
- Toutes les opérations ont un équivalent clavier : flèches pour déplacer,
  `Shift` pour la durée, `Alt` pour le début, `Entrée` pour éditer, `Suppr`
  pour supprimer, `Espace` pour activer.

### Éditeur et refus du sidecar

- `runFinal` retourne `Promise<boolean>` : `true` seulement si le sidecar a
  accepté le run.
- L'éditeur attend cette réponse. En cas de refus, il reste ouvert avec
  l'erreur moteur affichée, le bouton reprend son libellé et le brouillon reste
  corrigeable. Il ne se ferme que sur acceptation (ou si le patch ne change
  rien).

### Persistance du scénario

- Le dirty ne porte que sur le scénario : la graine est attachée au run et ne
  rend pas le scénario modifié. La persister avec le scénario serait un
  changement de contrat, hors phase 10.
- « Enregistrer le scénario » crée un nouveau `ScenarioRecord` ; l'upsert est
  une dette de la phase 13. `events` et `seasonality` sont préservés à chaque
  enregistrement.
- Une sauvegarde peut chevaucher une modification : après l'IPC, l'écran
  compare l'instantané réellement sauvegardé au scénario courant pour
  recalculer `dirty`, au lieu de le remettre à `false`.
- La navigation hors du cockpit **et** « Recharger l'application » passent par
  la même confirmation lorsque le scénario est modifié.

### Gardes clavier et focus

- `isTextEntryTarget` protège la saisie native (champs, `contenteditable`,
  `role=textbox`) ; `isInteractiveTarget` y ajoute les curseurs et séparateurs.
- `ownsActivationKeys` laisse `Espace`/`Entrée` activer boutons, liens,
  onglets, cases et menus : un `Espace` sur « Enregistrer » n'enregistre pas au
  lieu de lancer la lecture.
- Les dialogues posent `data-hotkeys-scope` sur leur racine ; tous les
  raccourcis de fond (y compris `Ctrl+K`, `Ctrl+S`, `Ctrl+Z/Y` et `Échap`) sont
  suspendus tant qu'ils sont ouverts.
- `useDialogFocus` place le focus initial, piège la tabulation, ferme sur
  `Échap` et restitue le focus au déclencheur.

## Contexte et raisons

- La revue de phase 10 a montré que les gardes globales et le mois KPI
  pouvaient produire des actions involontaires ou des chiffres faux.
- Les histogrammes mensuels sont volumineux : les envoyer dans les partiels
  contredirait le budget de fluidité de la phase 06.
- Un catalogue dupliqué à la main dérive silencieusement du moteur ; le
  générer et le vérifier en CI est la seule garantie durable.
- Un glissement ne doit jamais lancer un calcul par pixel : le coût moteur et
  la charge IPC deviennent incontrôlables.

## Alternatives

- **Calculer les histogrammes mensuels dans React à partir des runs** :
  interdit par la règle « aucun calcul métier dans React » et coûteux.
- **Ajouter une méthode IPC de catalogue** : surdimensionné pour une donnée
  statique, et impossible hors sidecar.
- **Sauvegarder le scénario à chaque modification** : écritures disque
  excessives, pas d'undo propre, et l'utilisateur perd le contrôle explicite.
- **Mettre la graine dans le dirty** : change le contrat de persistance et
  rendrait « modifié » un scénario pour un simple essai de graine.
- **Fermer l'éditeur après « Appliquer »** : l'utilisateur perd sa saisie si le
  moteur refuse ; l'attente explicite est meilleure.

## Conséquences

- Le protocole `1.11.0` est la base des phases 11 (`1.12.0`), 12 (`1.13.0`) et 13 (`1.14.0`).
- La CI exécute `catalog:check` avec le job Python.
- L'éditeur et la frise introduisent une dépendance à `runFinal(): Promise<boolean>` ;
  les appelants « feu et oubli » restent valides (`void live.runFinal()`).
- Les tests de phase 10 couvrent la géométrie, le playback, les raccourcis, le
  focus des dialogues, l'éditeur, la frise et les parcours d'intégration
  (ajout, undo/redo, refus sidecar, sauvegarde concurrente).
- L'upsert des scénarios et l'épinglage persistant restent des dettes de la
  phase 13.

## Vérification

- `npm run protocol:check` et `npm run catalog:check` sont verts.
- Le payload final contient 2 histogrammes par mois ; les partiels aucun.
- Changer de mois ne fait aucun appel `startSimulation`.
- Un glissement produit une commande et un `runFinal` au relâchement ;
  `pointercancel` n'en produit aucun.
- Un refus moteur laisse l'éditeur ouvert avec son message.
- Une modification pendant l'IPC de sauvegarde laisse le badge « Modifications
  non enregistrées ».
- `Espace` sur un bouton active le bouton ; un champ garde ses flèches ; un
  dialogue suspend tous les raccourcis de fond.
- `Échap` ferme le dialogue et rend le focus au déclencheur.
