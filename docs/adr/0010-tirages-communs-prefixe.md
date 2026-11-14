# ADR 0010 — Tirages communs et propriété de préfixe

- **Statut** : accepté, implémenté en phase 03
- **Date** : 2026-11-14
- **Contexte** : phase 01 (décision), phase 03 (mise en œuvre)
- **Remplace** : la stratégie d'échantillonnage de l'ADR 0003 (le générateur et la reproductibilité par graine sont conservés)

## Décision

Le moteur échantillonne à partir d'une **banque de tirages** explicite (`engine/draws.py`),
et non plus en appelant directement les distributions de `numpy.random.Generator` dans
l'ordre des clés.

1. **Deux flux de base par slot** : des uniformes `U(0,1)` et des normales standard `Z`.
   Les deux flux ont des séquences **indépendantes** et sont générés à la demande : une loi
   normale ne consomme que `Z`, une triangulaire que `U`. Le mapping est centralisé dans
   `distribution_streams()`.
2. **Identifiant de slot stable** : `slot_id = BLAKE2b(name, digest_size=8)` interprété en
   entier 64 bits non signé. Ajouter ou renommer un slot ne décale pas les autres.
3. **Générateur par bloc et par flux** :
   ```python
   seq = np.random.SeedSequence([seed, slot_id, block_index, stream])
   rng = np.random.Generator(np.random.PCG64(seq))
   ```
   avec `stream = 0` pour `U` et `stream = 1` pour `Z`. Le quatrième mot d'entropie est la
   seule déviation par rapport à la rédaction initiale de la phase 01 : il est nécessaire
   pour que générer un flux seul ne modifie jamais l'autre. Aucun appel à
   `SeedSequence.spawn()` dans un ordre variable.
4. **Tailles de bloc** :
   - `BLOCK_SIZE = 1024` pour les slots vectoriels (le bruit), afin de borner la mémoire
     par lot ;
   - `SCALAR_BLOCK_SIZE = 2048` pour les slots scalaires, dont le tableau complet est de
     toute façon matérialisé par le runner. Découper ces tableaux en blocs de 256 runs
     multipliait les générateurs et les concaténations sans économiser de mémoire.
5. **Slots nommés** :
   - `hyp:<clé>` pour chaque hypothèse résolue ;
   - `noise` pour le bruit mensuel, forme `(block, horizon)`, `squeeze=False` pour que
     l'horizon 1 reste bidimensionnel ;
   - `event:<id>:active`, `event:<id>:magnitude` (phase 05) ;
   - tout nouveau besoin déclare un slot explicite.
6. **Transformations sans aléa supplémentaire** : la valeur est une fonction déterministe de
   `U` et/ou `Z` (transformation normale, inversion de CDF, recherche dichotomique pour les
   lois empiriques). Un changement de paramètres ou de famille de loi ne change ni `U` ni
   `Z`.
7. **Propriété de préfixe** : pour tout `k ≤ n`, `take(slot, n)[:k] == take(slot, k)`. Elle
   est testée aux frontières de blocs (`250`, `256`, `257`, `500`, `1000`, `1023`, `1024`,
   `1025`, `2047`, `2048`) et comparée entre tailles de lots.
8. **Cache borné** : LRU de `16` blocs par banque, une entrée regroupant les flux d'un même
   `(slot, block_index)`. Une éviction provoque une régénération déterministe, jamais un
   changement de valeur. Avec des blocs de bruit de 1024 runs et 36 mois, le cache reste
   sous 10 Mio.
9. **Poisson** : inversion exacte de la CDF pour un `λ` scalaire. La table est construite en
   espace logarithmique (`log P(X=k)`, puis `cumsum`) pour rester stable quand `λ` grandit,
   et mise en cache par `λ`. Au-delà de `POISSON_EXACT_MAX = 50 000`, une approximation
   normale `N(λ, √λ)` est utilisée **et signalée** dans `SimulationResult.approximations`
   sous la forme `["poisson_normal"]`. Le champ est optionnel dans le protocole `1.8.0` :
   les résultats stockés sans lui restent lisibles.

## Contexte et raisons

- Le cockpit exige que bouger **un** paramètre ne fasse bouger que son effet. Sans CRN, les
  courbes « tremblent » à chaque calcul et les comparaisons de branches sont invalides.
- L'ancienne implémentation consommait un flux par hypothèse dans l'ordre trié, puis un flux
  de bruit séparé. Changer de famille de loi (`normal` → `triangulaire`) changeait la
  consommation d'uniformes et donc toute la suite.
- `rng.poisson` consomme un nombre variable d'uniformes : il n'est pas CRN pour un
  changement de `λ`.
- Le bruit en `(runs, horizon)` en une seule allocation est un risque mémoire pour les
  grands runs et empêche le calcul par blocs.
- Aucune garantie de préfixe n'était testée avant la phase 03.

## Alternatives

- **Garder l'ordre des clés et un flux unique** : simple, mais un ajout d'hypothèse décale
  tous les tirages ; impossible de garantir l'indépendance.
- **`SeedSequence.spawn()` par slot** : dépend de l'ordre des appels, donc fragile.
- **scipy.stats** : ajouterait une dépendance lourde au moteur, interdit par le plan.
- **Tirages indexés par run** : correct mais coûteux en mémoire et lent à générer
  aléatoirement.
- **Blocs uniformes de 256 runs pour tous les slots** : conforme à la rédaction initiale,
  mais mesuré à environ +7,5 % sur `final` 5 000 × 36. Les tailles de bloc et la génération
  paresseuse par flux ramènent la surcharge à environ +3 %.

## Conséquences

- `simulate()` n'appelle plus `rng.normal`, `rng.triangular`, `rng.poisson` ni `rng.choice`.
- Un slot inconnu est une erreur de programmation, pas un fallback silencieux.
- Le cache ne doit jamais être partagé entre deux `seed` ou deux horizons.
- Les tirages de base sont indexés par nom de slot, pas par position : ajouter une
  hypothèse ou un événement ne décale rien.
- Le golden `retail_depot_three_months` n'a pas changé : son scénario est entièrement
  déterministe (`demand_cv = 0`, aucune distribution), donc aucun tirage n'entre dans ses
  agrégats. Un scénario avec distributions produirait des valeurs de paramètres différentes
  de la phase 02 : le changement de méthode est assumé et documenté.
- Le numéro de version du moteur passe à `0.2.0`.
- L'ADR 0003 reste valide pour : PCG64 local, pas d'état global, `float64`, golden tests,
  absence de dépendance réseau/UI.

## Vérification

- Tests de préfixe et d'invariance dans `packages/engine/tests/test_draws.py` et
  `packages/engine/tests/test_crn.py` : frontières de blocs, changement de paramètres,
  changement de famille, ordre et ajout d'hypothèses, tailles de lots, cache vidé.
- Tests de lois et de Poisson de référence dans `tests/test_distributions.py`.
- Mesure perf : surcoût de **+3,0 %** sur `final` 5 000 × 36 (77,6 ms contre 75,3 ms pour
  la phase 02, `npm run bench` sur la machine de référence), sous la cible de 5 %.
- Cache de 16 blocs, soit moins de 10 Mio pour le bruit à 36 mois ; aucun tableau
  `runs × horizon × nombre_de_slots`.
