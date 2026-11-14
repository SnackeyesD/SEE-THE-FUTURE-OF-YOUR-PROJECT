# ADR 0013 — Vue 3D et repli obligatoire

- **Statut** : accepté
- **Date** : 2026-11-14
- **Contexte** : phase 01, s'applique en phase 14

## Décision

La vue 3D est un **complément**, jamais l'unique voie d'accès à une information.

- Pile : **Three.js** + **`@react-three/fiber`** + `drei` (contrôles et labels uniquement).
- **Chargement paresseux** : `React.lazy` + `Suspense` ; le chunk 3D ne fait pas partie du bundle initial.
- **Détection WebGL** au montage : tenter `webgl2`, puis `webgl` ; écouter `webglcontextlost`.
- **Repli automatique** vers la heatmap 2D si WebGL est absent, si le contexte est perdu, ou si les fps médians tombent sous 30 après 2 s de rendu.
- Le repli est expliqué à l'utilisateur, avec un bouton « rester en 2D » mémorisé par projet.
- **Rendu à la demande** (`frameloop="demand"`) ou suspendu hors écran (`IntersectionObserver`).
- `dpr={[1, 2]}` pour limiter le coût HiDPI.
- `dispose()` explicite des géométries, matériaux et textures au démontage.
- Nuage Monte Carlo : `Points` ou `InstancedMesh`, jamais un mesh par point ; maximum 5 000 points issus de runs réels.
- Aucune rotation automatique si `prefers-reduced-motion`.
- Aucun chiffre calculé en 3D : la scène rend les matrices fournies par la phase 11.

## Contexte et raisons

- WebKitGTK (Linux) n'offre pas toujours WebGL fiable ; les machines cibles n'ont pas de GPU dédié.
- Three.js pèse lourd : l'importer au démarrage dégraderait le temps de lancement et le bundle.
- La 3D est la **première fonctionnalité à couper** en cas de retard (plan §7). Elle doit donc être isolée et optionnelle.
- L'information doit rester disponible en 2D (heatmap, tableau), pour l'accessibilité et les machines sans WebGL.

## Alternatives

- **Pas de 3D** : acceptable et déjà prévu comme coupe ; l'ADR documente comment l'ajouter sans dette.
- **WebGL brut** : plus de contrôle, mais beaucoup de code de scène, de caméra et de picking à maintenir.
- **Babylon.js** : plus lourd, écosystème React moins direct.
- **Canvas 2.5D** : insuffisant pour une surface manipulable.

## Conséquences

- Le chunk 3D est budgété séparément (< 1,2 Mio gzip, plafond 1,6 Mio) et vérifié dans le manifeste de build.
- Les tests doivent couvrir : WebGL absent, contexte perdu, fps faible, mapping grille → sommets, raycast → coordonnées, appel de `dispose`.
- Aucune donnée par run n'est chargée sans passer par `simulation.trajectories` (phase 12).
- Un clic 3D produit la même commande qu'un clic heatmap (phase 08).
- La phase 14 est coupable sans impact sur les jalons A, B et D.

## Vérification

- Test sur Pop!_OS/Ubuntu (WebKitGTK) et sur une machine Windows modeste.
- Mesure fps (surface 15×15, nuage 5 000 points) et mémoire GPU.
- Vérification que le chunk 3D n'est pas chargé au démarrage.
- Vérification qu'aucune information n'est exclusive à la 3D.
