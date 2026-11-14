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

- [ ] `components/cockpit/Scene3D.tsx` en **import dynamique**.
- [ ] `components/cockpit/SurfaceMesh.tsx`, `PointCloud.tsx`, `CameraControls.tsx`.
- [ ] `lib/webgl.ts` : détection, perte de contexte, mesure fps.
- [ ] Bascule 3D ↔ heatmap avec préférence mémorisée.
- [ ] Tests de géométrie, de repli et de bundle.
- [ ] Mesures sur machine modeste et WebKitGTK.

## 4. Tâches détaillées

### Lot A — Socle 3D

- [ ] Dépendances : `three`, `@react-three/fiber`, `drei` (contrôles + labels). Vérifier les versions compatibles React 18.
- [ ] **Chargement paresseux** : `React.lazy` + `Suspense` ; le chunk 3D ne doit pas être dans le bundle initial.
- [ ] Budget : chunk 3D < 1,2 Mo gzip ; mesurer avec `vite build --report` ou équivalent.
- [ ] Canvas `dpr={[1, 2]}` pour limiter le coût sur écrans HiDPI.
- [ ] Boucle de rendu : `frameloop="demand"` ou suspension via `IntersectionObserver` quand le panneau n'est pas visible.
- [ ] Nettoyage : `dispose()` des géométries/matériaux/textures au démontage.

### Lot B — Surface

- [ ] Convertir la matrice `zP50` en géométrie : grille `xValues × yValues`, hauteur normalisée `z`.
- [ ] Couleurs par sommet issues de l'échelle 2D (mêmes tokens) ; légende HTML.
- [ ] Axes : libellés, unités, min/max, orientation cohérente avec la heatmap.
- [ ] Point courant : petit marqueur + ligne verticale ; libellé de valeur.
- [ ] Clic (raycast) sur la surface → coordonnées (x, y) → commande de réglage des deux paramètres ; confirmation visuelle.
- [ ] Option P10/P90 : surfaces translucides, désactivées par défaut (coût visuel).
- [ ] Mode top-down : caméra orthogonale au-dessus ; bouton « revenir à la heatmap ».

### Lot C — Nuage Monte Carlo

- [ ] Un point par run retenu (≤ 5 000) : x = investissement/paramètre choisi, y = mois de point mort, z = profit final.
- [ ] Couleur selon le résultat ; légende.
- [ ] `Points` ou `InstancedMesh`, pas un mesh par point.
- [ ] Survol : valeurs ; clic : sélectionne le run → panneau de provenance (phase 12).
- [ ] Si les données par run ne sont pas disponibles : masquer l'onglet avec explication, pas de nuage inventé.

### Lot D — Détection et repli

- [ ] `detectWebGL()` :
  - créer un canvas, tenter `webgl2` puis `webgl` ;
  - écouter `webglcontextlost` ;
  - retourner `{ supported, reason }`.
- [ ] Mesure fps : après 2 s de rendu, si médiane < 30 fps → proposer le repli (ne pas l'imposer brutalement).
- [ ] Repli automatique si WebGL absent ou contexte perdu ; afficher un message discret et la heatmap.
- [ ] Préférence utilisateur (« rester en 2D ») mémorisée par projet.
- [ ] Tests : WebGL mocké absent → heatmap ; fps faible → avertissement ; contexte perdu → repli.
- [ ] Tester sur Pop!_OS / Ubuntu (WebKitGTK) et Windows modeste.

### Lot E — Accessibilité et tests

- [ ] Aucune information uniquement en 3D : la heatmap et le tableau restent disponibles.
- [ ] Légende lisible, valeurs au survol, navigation clavier vers l'onglet 2D.
- [ ] `prefers-reduced-motion` : pas de rotation automatique.
- [ ] Tests :
  - géométrie (mapping grille → sommets) ;
  - raycast → coordonnées (test unitaire du mapping) ;
  - repli ;
  - chunk non chargé au démarrage (vérifier le manifest de build) ;
  - absence de fuite (dispose appelé).
- [ ] `ui:check` vert.

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

- [ ] La surface 3D s'affiche pour une surface calculée.
- [ ] Le clic règle les deux paramètres.
- [ ] Le nuage affiche ≤ 5 000 runs réels.
- [ ] Le repli 2D se déclenche sans erreur si WebGL manque ou est lent.
- [ ] Le chunk 3D n'est pas chargé au démarrage.
- [ ] Aucune information n'est exclusive à la 3D.
- [ ] Tests sur Linux (WebKitGTK) et Windows modeste consignés.
- [ ] Le rendu est suspendu hors écran.

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

- [ ] 3D + repli livrés ou phase coupée avec décision consignée.
- [ ] Budget bundle et fps mesurés.
- [ ] Tests WebKitGTK/Windows.
- [ ] Jalon C validé.
