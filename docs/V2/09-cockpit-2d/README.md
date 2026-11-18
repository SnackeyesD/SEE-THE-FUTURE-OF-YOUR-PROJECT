# Phase 09 — Cockpit 2D

> **Objectif** : livrer le vertical slice visible de la V3 — KPI, éventail P10–P90, seuil déplaçable, hypothèses à trois poignées, fantômes, convergence et graine — avec une interaction fluide et accessible.

**Références** : `V3-COCKPIT.md` §6, §7 (I1–I3, I9 partiel, I12), §9 ; plan maître C6, C8.
**Dépend de** : phase 08 (store/commandes/live), 02 (bandes), 06 (flux).
**Débloque** : 10, 11, 12, 13, 15.
**Profil** : senior TS/React + design ; 8–10 jours.
**Jalon A** : à la fin, on déplace un curseur et la courbe réagit de façon stable. **Premier test utilisateurs.**

---

## 1. Contexte

C'est la phase qui transforme la simulation en cockpit. Elle doit prouver trois choses :

1. la réactivité (draft/final) est crédible ;
2. les chiffres restent honnêtes (fourchettes, graine, convergence) ;
3. l'interface reste utilisable sur un PC modeste, sans casser le design system existant.

## 2. Périmètre

**Inclus**

- Écran `Cockpit` et ses panneaux.
- `FanChart` (bande P10–P90, médiane, fantômes, seuil glissable, sélection de mois).
- Barre KPI (point mort, financement, trésorerie, convergence, graine).
- Panneau d'hypothèses à trois poignées, verrou, source/confiance, saisie numérique.
- Fantômes de runs épinglés.
- Dispositions et plein écran (phase 08 fournit le conteneur).
- Accessibilité clavier et lecteur d'écran.
- Tests de composants et de géométrie.

**Exclu**

- Curseur de temps et événements (phase 10).
- Heatmap, tornado interactif, objectif (phase 11).
- 3D (phase 14).

## 3. Livrables

- [x] `apps/desktop/src/screens/CockpitScreen.tsx`.
- [x] `apps/desktop/src/components/cockpit/` : `KpiBar`, `FanChartPanel`, `HypothesesPanel`, `TriHandleSlider`, `ConvergenceBadge`, `SeedControl`, `GhostLegend`.
- [x] `packages/ui/src/viz/FanChart.tsx` (+ export dans `viz/index.ts`, styles `chart.css`).
- [x] Raccourcis de base (plein écran, focus panneau) ; les raccourcis complets arrivent en phase 10.
- [x] Tests Vitest et tests de géométrie.
- [ ] Captures et notes dans `docs/V2/09-cockpit-2d/`.

## 4. Tâches détaillées

### Lot A — Écran et composition

- [x] Route `cockpit` (ou remplacement de l'écran de résultats) sans casser `ResultsScreen`.
- [x] Composition :
  ```text
  KpiBar
  ├─ Hypothèses | FanChart (principal) | Secondaire (histogramme, tornado)
  └─ Frise / sélection de mois (socle posé ici, enrichi en phase 10)
  ```
- [x] Utiliser `PanelGrid` de la phase 08 ; presets `Analyse`, `Pilotage`, `Présentation`.
- [x] États : vide (pas de scénario), chargement initial, calcul en cours, erreur, résultat périmé.
- [x] Aucun chiffre calculé localement : tout vient de `SimulationAggregates`.

### Lot B — FanChart

- [x] API :
  ```ts
  type FanPoint = { month: number; p10: number; p50: number; p90: number };
  type GhostSeries = { id: string; label: string; points: FanPoint[]; seed: number };
  <FanChart
    points={fanPoints}
    ghosts={ghosts}
    threshold={{ value, label, onChange }}
    selectedMonth={month}
    onSelectMonth={(m) => ...}
  />
  ```
- [x] Rendu SVG : surface P10–P90, ligne P50, lignes fantômes, ligne de seuil glissable.
- [x] Le seuil est une **ligne horizontale** (trésorerie minimale) : le glisser met à jour `P(min cash < seuil)` à partir de la **CDF fournie par le moteur** (phase 02). L'interpolation linéaire entre deux points de CDF est autorisée ; aucun recalcul de simulation.
- [x] Si la CDF n'est pas disponible (ancien run), afficher « non disponible » — ne pas inventer.
- [x] Tooltip : mois, P10/P50/P90, seuil, probabilité de passer dessous.
- [x] Crosshair et sélection de mois au clic ; navigation clavier (flèches).
- [x] Fantômes : maximum 3, opacité réduite, légende avec graine et libellé.
- [x] Aucune animation de valeur ; transitions uniquement sur l'apparition/disparition de panneaux (reduced motion respecté).
- [x] Géométrie dans des fonctions pures (`scale.ts`, `fanPath.ts`) testées.

### Lot C — KPI

- [x] Afficher :
  - `P(point mort ≤ N mois)` avec sélecteur N (6 / 12 / 18 / horizon) ;
  - besoin de financement P50 et P90 ;
  - `P(trésorerie < 0)` ;
  - profit P50 avec P10–P90 en secondaire ;
  - badge de convergence ;
  - graine + bouton « relancer avec une autre graine » ;
  - version moteur.
- [x] Chaque KPI porte une infobulle « définition » et la graine.
- [x] Clic sur un KPI → panneau de provenance (phase 12) ; en attendant, tooltip explicatif.
- [x] Les probabilités sont affichées en %, avec le nombre de runs et `runsRetained`.

### Lot D — Panneau d'hypothèses

- [x] `TriHandleSlider` :
  - trois poignées min / mode / max sur une échelle ;
  - contrainte `min ≤ mode ≤ max` (les poignées ne se croisent pas) ;
  - aperçu de la distribution (petit SVG) ;
  - clavier : chaque poignée focusable, flèches ±1 pas, Page↑/↓ ±10 pas, Home/End ;
  - `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, `aria-valuetext` avec unité ;
  - double-clic pour saisie numérique ;
  - verrou (le paramètre reste fixe) ;
  - badges source (`user`, `benchmark`, `estimate`) et confiance ;
  - valeur de référence du benchmark au survol si disponible (`benchmark.lookup` du sidecar) ;
  - bouton « revenir au benchmark ».
- [x] Afficher la valeur centrale, l'unité, et la fourchette.
- [x] Grouper par thème (prix, coûts, demande, stock, finance) sans coder de logique métier en dur si le modèle peut l'exposer.
- [x] Le panneau est scrollable indépendamment ; pas de perte de focus pendant les partiels.
- [x] Chaque changement produit une commande coalescée (phase 08).

### Lot E — Fantômes et comparaison minimale

- [ ] Épingler le run final courant (bouton + raccourci) : stocke `runId`, graine, libellé, agrégats.
- [ ] Les fantômes sont persistés (phase 07, `pinned`) et rechargés à l'ouverture.
- [x] Afficher un avertissement si deux runs n'ont pas la même graine : la comparaison reste possible mais **signalée**.
- [x] La comparaison complète (diff, côte à côte) est en phase 13.

### Lot F — Accessibilité et tests

- [x] Vérifier contrastes avec les tokens existants ; aucune information portée par la seule couleur.
- [x] Fournir un tableau alternatif repliable (mois, P10/P50/P90) pour le graphique.
- [x] Focus visible, ordre logique, pas de piège au clavier.
- [x] `prefers-reduced-motion` : pas de transition de valeur.
- [x] Tests :
  - `fanPath` : ordre des points, trous, une seule valeur ;
  - `TriHandleSlider` : clavier, contraintes, double-clic, undo ;
  - `KpiBar` : formatage, absence de données → « non disponible » ;
  - `CockpitScreen` : draft → partiel → final avec IPC factice ;
  - run périmé ignoré.
- [x] Vérifier `npm run ui:check` (pas de couleur en dur, pas de classe morte).

## 5. Contrats et formatage

```ts
type FanData = {
  months: number[];
  profit: FanPoint[];
  cash: FanPoint[];
  breakEvenProbability: number[]; // cumulée par mois
  runsRetained: number;
};
```

- Montants : `formatCurrency` existant, devise du scénario.
- Probabilités : 1 décimale, jamais `100 %` si la borne haute n'est pas certaine.
- Mois : 1-based côté affichage.
- Graine : toujours visible dans le KPI et dans la légende des fantômes.

## 6. Pièges

- **Recalculer la probabilité de seuil dans l'UI** : interdit. Demander au moteur ou afficher « non disponible ».
- **Interpoler les courbes pour faire croire à du 50 fps** : interdit ; on peut animer l'**apparition** d'un résultat, jamais ses valeurs.
- **Changer les bornes de l'histogramme** en cours de calcul : voir phase 04.
- **Trop de fantômes** : maximum 3, sinon illisible et coûteux.
- **Trois poignées** : la contrainte min ≤ mode ≤ max doit être appliquée pendant le drag, pas seulement à la validation.
- **Focus perdu** : un partiel toutes les 50 ms ne doit pas démonter le panneau d'hypothèses.
- **Palette** : utiliser les tokens ; `ui:check` échoue sinon.

## 7. Critères d'acceptation

- [x] Déplacer un curseur met à jour l'éventail de façon fluide et stable (pas de tremblement).
- [x] Le résultat `final` remplace le `draft` au relâchement, avec la même graine.
- [x] Le seuil est glissable et la probabilité affichée est fournie par le moteur.
- [x] Les trois poignées sont utilisables à la souris et au clavier.
- [x] L'utilisateur peut épingler un run et le voir en fantôme.
- [x] La graine et la convergence sont visibles en permanence.
- [x] Aucun chiffre n'est calculé dans React.
- [x] `ui:check`, `typecheck`, tests UI verts.
- [ ] Test utilisateur réalisé (3–4 personnes) et consigné.

## 8. Performance

| Mesure | Cible |
|---|---|
| Mise à jour du FanChart (36 points + 3 fantômes) | ≤ 16 ms |
| Traitement d'un partiel | ≤ 4 ms |
| Glissement à 30–60 i/s | sans chute > 2 frames |
| Mémoire UI | < 100 Mo |

## 9. Risques

| Risque | Mitigation |
|---|---|
| Tremblement des courbes | CRN testé, pas de recalcul local |
| Panneau d'hypothèses illisible | Grouper, valeurs secondaires repliées |
| Accessibilité oubliée | Checklist + tests clavier |
| Design system cassé | Tokens, `ui:check`, revue design |
| Perf sur PC modeste | SVG simple, memo, mesure |

## 10. Definition of Done

- [x] Cockpit A livré et utilisable de bout en bout.
- [x] Tests UI et géométrie verts.
- [x] Accessibilité clavier validée.
- [ ] Captures et retour du test utilisateur consignés.
- [ ] Jalon A validé ou décision de coupe documentée.

---

## 11. Mise en œuvre (2026-11-18)

### Livré

- **Route `cockpit`** dans `App.tsx`, entre Résultats et Réglages. `ResultsScreen`
  reste intact et `suggestedView` continue de pointer sur `results` : le parcours
  existant et les tests d'App ne changent pas.
- `CockpitScreen` monte un `CockpitProvider` par couple projet/scénario
  (`key={projectId:scenarioId}`), réhydrate le run persisté (`hydrateRun`) et prend la
  graine du run (`result.seed ?? run.seed ?? 42`).
- **Composition** : `KpiBar` en tête, `PanelGrid` (phase 08) avec hypothèses à gauche,
  éventail au centre, histogramme + tornado à droite, frise de mois et actions en pied.
  Les boutons de plein écran de `PanelGrid` servent de raccourcis de base ; les raccourcis
  clavier complets restent en phase 10.
- **`packages/ui/src/viz/fan.ts`** : géométrie pure (`normalizeFanPoints`, `fanDomain`,
  `fanBandPath`, `fanLinePath`), CDF (`normalizeCdf`, `cdfProbabilityAt`), sélection
  (`nearestMonth`) et pas clavier (`thresholdStep`).
- **`FanChart`** : surface P10–P90, médiane, trois fantômes maximum, seuil horizontal
  glissable ou clavier (`role="slider"`, flèches, Page↑/↓, Home/End), crosshair et
  sélection de mois (flèches sur le groupe), tableau alternatif repliable, libellés
  `aria` et probabilité issue de la CDF. Aucune transition de valeur.
- **`components/cockpit/`** : `KpiBar`, `FanChartPanel`, `HypothesesPanel`,
  `TriHandleSlider`, `ConvergenceBadge`, `SeedControl`, `GhostLegend`.
- **Hypothèses** : specs communes dans `src/lib/assumptions.ts` (réutilisées par
  `HypothesesScreen`), groupes prix/coûts/demande/stock/finance, badges source/confiance,
  bouton de retour au benchmark, verrou UI et commande coalescée par geste.
- **Contrôleur** : pendant un geste, `invalidate()` programme des drafts throttlés 50 ms
  et **aucun final** ; `endGesture()` ne lance le final que si le geste a modifié une
  entrée (`gestureDirty`). Un run remplacé est marqué `cancelled` localement avant le
  `start` suivant.
- **Formatage** : `formatProbability` borne les extrêmes (« ≥ 99,9 % », « ≤ 0,1 % »,
  jamais « 100 % ») et `formatCurrency` reste la seule source pour les montants.

### Tests

44 tests ajoutés, 107 tests desktop au total :

| Fichier | Tests |
|---|---|
| `components/cockpit/fan.test.ts` | 16 (ordre, trous, domaine, CDF, pas) |
| `components/cockpit/FanChart.test.tsx` | 7 (rendu, seuil clavier, mois, fantômes) |
| `components/cockpit/TriHandleSlider.test.tsx` | 8 (clavier, contraintes, saisie, verrou) |
| `components/cockpit/KpiBar.test.tsx` | 5 (formatage, mois, « non disponible », graine) |
| `screens/CockpitScreen.test.tsx` | 8 (scénario, épinglage, final IPC, périmé, verrou, onglets) |

`npm run typecheck`, `npm run lint` (dont `ui:check`) et `npm run test -w @see/desktop`
sont verts.

### Limites connues et reports

- **Fantômes non persistés** : le protocole `1.10.0` n'expose ni `run.list` ni
  `run.pin`. L'épinglage vit dans le store de session (maximum 3 dessinés) et disparaît
  au rechargement. La persistance et la comparaison complète arrivent en phase 13.
- **Verrou d'hypothèse local** : état UI uniquement ; le moteur n'a pas de paramètre
  verrouillé et le protocole ne change pas.
- **Benchmark au survol** : le panneau affiche le libellé de provenance et le bouton
  « revenir au benchmark » ; l'appel `benchmark.lookup` au survol reste dans l'écran
  Hypothèses (pas de nouvel appel par curseur).
- **Raccourci d'épinglage** : seul le bouton est câblé ; le raccourci clavier complet
  est en phase 10.
- **Synchronisation App/Results** : le cockpit a son store ; les écrans historiques
  gardent leur état. La convergence des deux sources est prévue avec la refonte de la
  navigation (phases 10–12).
- **Test utilisateur et captures** non réalisés dans cet environnement ; le jalon A
  reste à valider avec 3–4 personnes.
