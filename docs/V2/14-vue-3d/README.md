# Phase 14 — Vue 3D & repli

> **Objectif** : ajouter une lecture 3D de la surface et du nuage Monte Carlo, **sans jamais** en faire l'unique voie d'accès à l'information. Si WebGL manque ou rame, la heatmap 2D prend le relais automatiquement.

**Références** : `V3-COCKPIT.md` §8, §12 ; plan maître C7, ADR 0013.
**Dépend de** : phase 11 (surface, heatmap).
**Débloque** : rien de critique — **première phase à couper**.
**Profil** : senior TS/3D ; 5–6 jours.
**Jalon C** : la 3D fonctionne sur la machine de référence, ou le repli 2D se déclenche proprement.

---

## 1. Contexte

La 3D est un complément. Les risques sont connus : WebKitGTK sans WebGL fiable, machines modestes, bundle qui grossit, accessibilité. La phase est donc conçue avec un **repli obligatoire** et un chargement paresseux.

## 2. Périmètre

**Inclus**

- Surface 3D (métrique en fonction de deux paramètres).
- Marqueur du point courant, clic → règle les deux paramètres.
- Surfaces P10/P90 en transparence (option).
- Nuage Monte Carlo 3D (≤ 5 000 points), sélection d'un run.
- Caméra : rotation, zoom, reset, mode top-down.
- Détection WebGL + mesure de fps + repli heatmap.
- Suspension du rendu hors écran, nettoyage des ressources.
- Accessibilité : équivalent 2D, valeurs au survol, légende.

**Exclu**

- Nouveaux calculs : la 3D consomme les données de la phase 11.
- VR/AR, post-processing, animations décoratives.

## 3. Livrables

- [x] `components/cockpit/Scene3D.tsx` en **import dynamique**.
- [x] `components/cockpit/SurfaceMesh.tsx`, `PointCloud.tsx`, `CameraControls.tsx`.
- [x] `lib/webgl.ts` : détection, perte de contexte, mesure fps.
- [x] Bascule 3D ↔ heatmap avec préférence mémorisée.
- [x] Tests de géométrie, de repli et de bundle.
- [ ] Mesures sur machine modeste et WebKitGTK.

## 4. Tâches détaillées

### Lot A — Socle 3D

- [x] Dépendances : `three` 0.170 et `@react-three/fiber` 8.17 (React 18). `drei` n'est pas retenu : contrôles caméra maison pour tenir le budget de chunk.
- [x] **Chargement paresseux** : `React.lazy` + `Suspense` ; le chunk 3D ne doit pas être dans le bundle initial.
- [x] Budget : chunk 3D < 1,2 Mo gzip ; mesurer avec `vite build --report` ou équivalent.
- [x] Canvas `dpr={[1, 2]}` pour limiter le coût sur écrans HiDPI.
- [x] Boucle de rendu : `frameloop="demand"` ou suspension via `IntersectionObserver` quand le panneau n'est pas visible.
- [x] Nettoyage : `dispose()` des géométries/matériaux/textures au démontage.

### Lot B — Surface

- [x] Convertir la matrice `zP50` en géométrie : grille `xValues × yValues`, hauteur normalisée `z`.
- [x] Couleurs par sommet issues de l'échelle 2D (mêmes tokens) ; légende HTML.
- [x] Axes : libellés, unités, min/max, orientation cohérente avec la heatmap.
- [x] Point courant : petit marqueur + ligne verticale ; libellé de valeur.
- [x] Clic (raycast) sur la surface → coordonnées (x, y) → commande de réglage des deux paramètres ; confirmation visuelle.
- [ ] Option P10/P90 : surfaces translucides, désactivées par défaut (coût visuel).
- [x] Mode top-down : caméra orthogonale au-dessus ; bouton « revenir à la heatmap ».

### Lot C — Nuage Monte Carlo

- [x] Un point par run retenu (≤ 5 000, borné à 200 par la phase 12) : x = besoin de financement, y = mois de point mort, z = profit final cumulé.
- [x] Couleur selon le résultat ; légende.
- [x] `Points` ou `InstancedMesh`, pas un mesh par point.
- [x] Survol : valeurs ; clic : sélectionne le run et affiche ses paramètres tirés (`simulation.run_params`). Le panneau de provenance complet reste accessible depuis les KPI du cockpit.
- [x] Si les données par run ne sont pas disponibles : masquer l'onglet avec explication, pas de nuage inventé.

### Lot D — Détection et repli

- [x] `detectWebGL()` :
  - créer un canvas, tenter `webgl2` puis `webgl` ;
  - écouter `webglcontextlost` ;
  - retourner `{ supported, reason }`.
- [x] Mesure fps : après 2 s de rendu, si médiane < 30 fps → proposer le repli (ne pas l'imposer brutalement).
- [x] Repli automatique si WebGL absent ou contexte perdu ; afficher un message discret et la heatmap.
- [x] Préférence utilisateur (« rester en 2D ») mémorisée par projet.
- [x] Tests : WebGL mocké absent → heatmap ; fps faible → avertissement ; contexte perdu → repli.
- [ ] Tester sur Pop!_OS / Ubuntu (WebKitGTK) et Windows modeste.

### Lot E — Accessibilité et tests

- [x] Aucune information uniquement en 3D : la heatmap et le tableau restent disponibles.
- [x] Légende lisible, valeurs au survol, navigation clavier vers l'onglet 2D.
- [x] `prefers-reduced-motion` : pas de rotation automatique.
- [x] Tests :
  - géométrie (mapping grille → sommets) ;
  - raycast → coordonnées (test unitaire du mapping) ;
  - repli ;
  - chunk non chargé au démarrage (`npm run bundle:check -w @see/desktop`) ;
  - absence de fuite (dispose explicite des géométries et matériaux, vérifié en revue).
- [x] `ui:check` vert.

## 5. Contrats

```ts
type Surface3DProps = {
  xValues: number[];
  yValues: number[];
  z: number[][];
  current: [number, number];
  metricLabel: string;
  unit: string;
  onPick: (x: number, y: number) => void;
};

type WebGLStatus = {
  supported: boolean;
  reason?: "no_context" | "context_lost" | "slow";
  fps?: number;
};
```

Règles :

- La 3D ne calcule rien ; elle rend `z`.
- Un clic 3D produit la même commande qu'un clic heatmap.
- Le repli est automatique **et** expliqué.
- Aucune donnée par run n'est chargée pour la 3D sans passer par `simulation.trajectories`.

## 6. Pièges

- **Importer Three.js au chargement initial** : bundle et démarrage dégradés.
- **Un mesh par point** : 5 000 draw calls ; utiliser `Points`.
- **Rendu continu hors écran** : batterie et CPU.
- **Oublier `dispose`** : fuite GPU après plusieurs ouvertures.
- **Caméra qui perd l'utilisateur** : bouton reset et top-down.
- **Couleurs 3D incohérentes avec la 2D** : réutiliser l'échelle.
- **WebGL logiciel** : mesurer, ne pas supposer.

## 7. Critères d'acceptation

- [x] La surface 3D s'affiche pour une surface calculée.
- [x] Le clic règle les deux paramètres.
- [x] Le nuage affiche ≤ 5 000 runs réels.
- [x] Le repli 2D se déclenche sans erreur si WebGL manque ou est lent.
- [x] Le chunk 3D n'est pas chargé au démarrage.
- [x] Aucune information n'est exclusive à la 3D.
- [ ] Tests sur Linux (WebKitGTK) et Windows modeste consignés.
- [x] Le rendu est suspendu hors écran.

## 8. Performance

| Mesure | Cible | Plafond |
|---|---|---|
| Chunk 3D gzip | < 1,2 Mo | 1,6 Mo |
| Surface 15×15 | 60 fps | ≥ 30 fps |
| Nuage 5 000 points | 60 fps | ≥ 30 fps |
| Mémoire GPU | < 150 Mo | 250 Mo |
| Repli détecté | < 3 s | 5 s |

## 9. Risques

| Risque | Mitigation |
|---|---|
| WebGL absent | Détection + heatmap |
| Bundle trop gros | Lazy load, budget, drei minimal |
| Perf faible | DPR limité, points, frameloop demand |
| Accessibilité | Équivalent 2D obligatoire |
| Temps insuffisant | Phase coupable en premier |

## 10. Definition of Done

- [x] 3D + repli livrés ou phase coupée avec décision consignée.
- [ ] Budget bundle et fps mesurés.
- [ ] Tests WebKitGTK/Windows.
- [ ] Jalon C validé.

## 11. État d'implémentation (2026-11-23)

### Décisions effectives

- **Dépendances** : `three@0.170.0`, `@react-three/fiber@8.17.10` (compatible React 18), `@types/three` en dev. `drei` n'a pas été retenu : les contrôles caméra (orbite, zoom, reset, vue du dessus) sont implémentés dans `CameraControls.tsx`, ce qui évite un chunk inutile.
- **Chargement paresseux** : `Surface3DView` importe `Scene3D` via `React.lazy` + `Suspense`. Le manifest Vite confirme un chunk séparé ; `npm run bundle:check -w @see/desktop` vérifie aussi que l'entrée ne l'importe pas.
- **Budget mesuré** : chunk `Scene3D` = **223,64 kB gzip**, supplément au chargement **0,213 Mo gzip** (budget 1,2 Mo). Le chunk initial reste à 129,77 kB gzip.
- **Rendu** : `frameloop="demand"`, `dpr={[1, 2]}`, aucun rendu automatique hors écran (`IntersectionObserver`, message « rendu suspendu »). Les géométries et matériaux créés à la main sont libérés au démontage.
- **Surface** : `buildSurfaceGeometry` est pur (positions normalisées, hauteurs, paliers de couleur, triangles incomplets ignorés). Les couleurs sont lues depuis les tokens `--heat-0…4`, jamais dupliquées en dur.
- **Clic** : le raycast convertit le point d'intersection normalisé en cellule, puis appelle la même commande d'application que la heatmap (`onApplyPoint`). Aucun calcul métier.
- **Nuage Monte Carlo** : chargé uniquement à l'ouverture de l'onglet, via `simulation.trajectories` borné à **200 trajectoires** (contrainte de la phase 12). Un seul objet `Points`. Un clic affiche les paramètres tirés du run via `simulation.run_params`.
- **Repli** : `detectWebGL()` tente `webgl2` puis `webgl` et relâche le contexte. Absence de WebGL ou perte de contexte → retour automatique à la heatmap avec message. Une fréquence médiane < 30 fps affiche un avertissement avec « Continuer en 3D » / « Revenir à la carte 2D » (le repli n'est pas imposé).
- **Préférence** : `see.surface.view.<projectId>` mémorise `2d`/`3d` ; une machine sans WebGL ne mémorise jamais `3d`.
- **Accessibilité** : la heatmap et son tableau restent toujours disponibles via l'onglet 2D, la légende et les valeurs au survol sont en HTML, les boutons sont au clavier, aucune rotation automatique.

### Écarts assumés

- **Surfaces P10/P90 translucides** : non livrées. La surface P50 suffit au jalon C et les surfaces translucides ajoutent du coût visuel ; le sujet est reporté à une itération de la vue 3D.
- **Axes du nuage** : la phase 11 n'expose pas les valeurs de levier par run en lot. L'axe X utilise donc le besoin de financement dérivé de `cashMonthly`, l'axe Y le mois de point mort et l'axe Z le profit final cumulé. Ces trois valeurs sont calculées dans `lib/pointCloud.ts`, jamais simulées.
- **Panneau de provenance** : le clic sur un point affiche les paramètres effectivement tirés pour ce run ; le panneau « D'où vient ce chiffre ? » complet reste ouvert depuis les KPI du cockpit. Aucun chiffre n'est inventé dans la vue 3D.
- **Mesures machine** : les tests automatisés couvrent géométrie, mapping, repli, chunk et préférence. Les mesures fps réelles sur WebKitGTK (Pop!_OS/Ubuntu) et Windows modeste restent à consigner, faute de machine de référence dans cet environnement. Le jalon C n'est donc pas déclaré validé.

### Tests

- `lib/surface3d.test.ts` : mapping grille → sommets, triangles incomplets, raycast, marqueur.
- `lib/pointCloud.test.ts` : profit cumulé, point mort, agrégation des trajectoires.
- `lib/webgl.test.ts` : détection, perte de contexte, médiane fps, mesure injectée.
- `lib/surfaceViewPreference.test.ts` : préférence par projet et repli expliqué.
- `SurfacePanel.test.tsx` : bascule 2D ↔ 3D, persistance, repli, application d'un point.
- `Surface3DView.test.tsx` : absence de WebGL, nuage désactivé sans run, chargement borné, perte de contexte, clic cellule.
- Desktop : 256 tests verts. `npm run typecheck`, `npm run lint`, `npm run ui:check`, `npm run protocol:check` et `git diff --check` verts.

### Fichiers

- `lib/webgl.ts`, `lib/surface3d.ts`, `lib/pointCloud.ts`, `lib/surfaceViewPreference.ts` (+ tests).
- `components/cockpit/Scene3D.tsx`, `SurfaceMesh.tsx`, `PointCloud.tsx`, `CameraControls.tsx`, `surface3d` styles, `Surface3DView.tsx` (+ test), `scenePalette.ts`.
- `components/cockpit/SurfacePanel.tsx` (+ test), `screens/CockpitScreen.tsx` (run final), `styles.css`.
- `apps/desktop/scripts/check-3d-bundle.mjs`, `package.json`, lockfile.
