# ADR 0003 — Moteur Monte Carlo reproductible avec numpy

- **Statut** : accepté
- **Date** : 2026-11-08
- **Contexte** : phase 02

## Décision

Le moteur `packages/engine` utilise **Python 3.11 + numpy** (sans autre dépendance de calcul)
et garantit la reproductibilité par une graine explicite :

- `numpy.random.Generator(PCG64(seed))` pour l'échantillonnage des hypothèses ;
- un flux séparé `PCG64(SeedSequence([seed, 0x5EED]))` pour le bruit mensuel ;
- aucun recours à l'état aléatoire global de numpy ;
- ordre d'échantillonnage fixé (clés d'hypothèses triées) ;
- gamma de calcul en `float64` ;
- golden tests déterministes dans `packages/engine/tests/golden/`.

## Contexte et raisons

- Le produit doit pouvoir afficher « même scénario + même graine = mêmes chiffres ».
- numpy suffit pour la vectorisation et tient la cible de performance desktop.
- Des flux aléatoires séparés évitent qu'un changement local (ajout d'une hypothèse ou d'un
  bruit) décale toute la séquence.
- La pré-génération des tirages et le découpage en lots rendent le résultat indépendant de
  la taille des lots, aux erreurs d'arrondi flottant près.
- Le moteur doit rester utilisable hors ligne, sans Tauri ni réseau.

## Alternatives

- **pandas / scipy** : plus de surface et de poids pour un besoin qui se limite à des
  tirages et à des agrégats simples.
- **Boucle Python par run** : trop lente pour 100 000 runs interactifs.
- **Graine globale `numpy.random.seed`** : non locale, fragile et difficile à tester.

## Conséquences

- numpy est épinglé par version majeure ; toute montée de version doit rejouer les golden
  tests et le benchmark.
- `runId` et `durationMs` sont exclus des comparaisons de reproductibilité.
- Les tirages pré-générés consomment de la mémoire proportionnellement à `runs × horizon` ;
  le plafond de runs est fixé à 1 000 000.
- Les agrégats mensuels sont accumulés par lots : une différence de taille de lot peut
  produire des écarts d'arrondi flottant négligeables, jamais un changement de distribution.
