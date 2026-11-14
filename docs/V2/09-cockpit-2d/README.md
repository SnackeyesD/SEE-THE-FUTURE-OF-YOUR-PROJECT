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

- [ ] `apps/desktop/src/screens/CockpitScreen.tsx`.
- [ ] `apps/desktop/src/components/cockpit/` : `KpiBar`, `FanChartPanel`, `HypothesesPanel`, `TriHandleSlider`, `ConvergenceBadge`, `SeedControl`, `GhostLegend`.
- [ ] `packages/ui/src/viz/FanChart.tsx` (+ export dans `viz/index.ts`, styles `chart.css`).
- [ ] Raccourcis de base (plein écran, focus panneau) ; les raccourcis complets arrivent en phase 10.
- [ ] Tests Vitest et tests de géométrie.
- [ ] Captures et notes dans `docs/V2/09-cockpit-2d/`.

## 4. Tâches détaillées

### Lot A — Écran et composition

- [ ] Route `cockpit` (ou remplacement de l'écran de résultats) sans casser `ResultsScreen`.
- [ ] Composition :
  ```text
  KpiBar
  ├─ Hypothèses | FanChart (principal) | Secondaire (histogramme, tornado)
  └─ Frise / sélection de mois (socle posé ici, enrichi en phase 10)
  ```
- [ ] Utiliser `PanelGrid` de la phase 08 ; presets `Analyse`, `Pilotage`, `Présentation`.
- [ ] États : vide (pas de scénario), chargement initial, calcul en cours, erreur, résultat périmé.
- [ ] Aucun chiffre calculé localement : tout vient de `SimulationAggregates`.

### Lot B — FanChart

- [ ] API :
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
- [ ] Rendu SVG : surface P10–P90, ligne P50, lignes fantômes, ligne de seuil glissable.
- [ ] Le seuil est une **ligne horizontale** (trésorerie minimale) : le glisser met à jour `P(min cash < seuil)` à partir de la **CDF fournie par le moteur** (phase 02). L'interpolation linéaire entre deux points de CDF est autorisée ; aucun recalcul de simulation.
- [ ] Si la CDF n'est pas disponible (ancien run), afficher « non disponible » — ne pas inventer.
- [ ] Tooltip : mois, P10/P50/P90, seuil, probabilité de passer dessous.
- [ ] Crosshair et sélection de mois au clic ; navigation clavier (flèches).
- [ ] Fantômes : maximum 3, opacité réduite, légende avec graine et libellé.
- [ ] Aucune animation de valeur ; transitions uniquement sur l'apparition/disparition de panneaux (reduced motion respecté).
- [ ] Géométrie dans des fonctions pures (`scale.ts`, `fanPath.ts`) testées.

### Lot C — KPI

- [ ] Afficher :
  - `P(point mort ≤ N mois)` avec sélecteur N (6 / 12 / 18 / horizon) ;
  - besoin de financement P50 et P90 ;
  - `P(trésorerie < 0)` ;
  - profit P50 avec P10–P90 en secondaire ;
  - badge de convergence ;
  - graine + bouton « relancer avec une autre graine » ;
  - version moteur.
- [ ] Chaque KPI porte une infobulle « définition » et la graine.
- [ ] Clic sur un KPI → panneau de provenance (phase 12) ; en attendant, tooltip explicatif.
- [ ] Les probabilités sont affichées en %, avec le nombre de runs et `runsRetained`.

### Lot D — Panneau d'hypothèses

- [ ] `TriHandleSlider` :
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
- [ ] Afficher la valeur centrale, l'unité, et la fourchette.
- [ ] Grouper par thème (prix, coûts, demande, stock, finance) sans coder de logique métier en dur si le modèle peut l'exposer.
- [ ] Le panneau est scrollable indépendamment ; pas de perte de focus pendant les partiels.
- [ ] Chaque changement produit une commande coalescée (phase 08).

### Lot E — Fantômes et comparaison minimale

- [ ] Épingler le run final courant (bouton + raccourci) : stocke `runId`, graine, libellé, agrégats.
- [ ] Les fantômes sont persistés (phase 07, `pinned`) et rechargés à l'ouverture.
- [ ] Afficher un avertissement si deux runs n'ont pas la même graine : la comparaison reste possible mais **signalée**.
- [ ] La comparaison complète (diff, côte à côte) est en phase 13.

### Lot F — Accessibilité et tests

- [ ] Vérifier contrastes avec les tokens existants ; aucune information portée par la seule couleur.
- [ ] Fournir un tableau alternatif repliable (mois, P10/P50/P90) pour le graphique.
- [ ] Focus visible, ordre logique, pas de piège au clavier.
- [ ] `prefers-reduced-motion` : pas de transition de valeur.
- [ ] Tests :
  - `fanPath` : ordre des points, trous, une seule valeur ;
  - `TriHandleSlider` : clavier, contraintes, double-clic, undo ;
  - `KpiBar` : formatage, absence de données → « non disponible » ;
  - `CockpitScreen` : draft → partiel → final avec IPC factice ;
  - run périmé ignoré.
- [ ] Vérifier `npm run ui:check` (pas de couleur en dur, pas de classe morte).

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

- [ ] Déplacer un curseur met à jour l'éventail de façon fluide et stable (pas de tremblement).
- [ ] Le résultat `final` remplace le `draft` au relâchement, avec la même graine.
- [ ] Le seuil est glissable et la probabilité affichée est fournie par le moteur.
- [ ] Les trois poignées sont utilisables à la souris et au clavier.
- [ ] L'utilisateur peut épingler un run et le voir en fantôme.
- [ ] La graine et la convergence sont visibles en permanence.
- [ ] Aucun chiffre n'est calculé dans React.
- [ ] `ui:check`, `typecheck`, tests UI verts.
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

- [ ] Cockpit A livré et utilisable de bout en bout.
- [ ] Tests UI et géométrie verts.
- [ ] Accessibilité clavier validée.
- [ ] Captures et retour du test utilisateur consignés.
- [ ] Jalon A validé ou décision de coupe documentée.
