# ADR 0010 — Tirages communs et propriété de préfixe

- **Statut** : accepté
- **Date** : 2026-11-14
- **Contexte** : phase 01, complète l'ADR 0003
- **Remplace** : la stratégie d'échantillonnage de l'ADR 0003 (le générateur et la reproductibilité par graine sont conservés)

## Décision

Le moteur échantillonne désormais à partir d'une **banque de tirages** explicite, et non plus en appelant directement les distributions de `numpy.random.Generator` dans l'ordre des clés.

1. **Deux tirages de base par slot** : des uniformes `U(0,1)` et des normales standard `Z`, générés par blocs de **256 runs**.
2. **Identifiant de slot stable** : `slot_id = BLAKE2b(name, digest_size=8)` interprété en entier 64 bits non signé. Ajouter ou renommer un slot ne décale pas les autres.
3. **Générateur par bloc** :
   ```python
   seq = np.random.SeedSequence([seed, slot_id, block_index])
   rng = np.random.Generator(np.random.PCG64(seq))
   ```
   Aucun appel à `SeedSequence.spawn()` dans un ordre variable.
4. **Slots nommés** :
   - `hyp:<clé>` pour chaque hypothèse résolue ;
   - `noise` pour le bruit mensuel, forme `(block, horizon)` ;
   - `event:<id>:active`, `event:<id>:magnitude` (phase 05) ;
   - tout nouveau besoin déclare un slot explicite.
5. **Transformations sans aléa supplémentaire** : la valeur est une fonction déterministe de `U` et/ou `Z` (inversion de CDF, transformation normale, recherche dichotomique pour les lois empiriques). Un changement de paramètres de loi ne change ni `U` ni `Z`.
6. **Propriété de préfixe** : pour tout `k ≤ n`, `take(slot, n)[:k] == take(slot, k)`. Elle est testée aux frontières de blocs (`250`, `256`, `257`, `500`, `1000`).
7. **Cache borné** : LRU de 64 blocs par `(seed, horizon, slot)` ; un cache plein provoque une régénération déterministe, jamais un changement de valeur.
8. **Poisson** : inversion exacte de la CDF pour un `λ` scalaire, avec table construite jusqu'à `1 − 1e-12`. Au-delà d'une taille raisonnable (ex. 100 000 entrées), une approximation normale est utilisée **et signalée** dans les métadonnées du résultat (`approximations: ["poisson_normal"]`).

## Contexte et raisons

- Le cockpit exige que bouger **un** paramètre ne fasse bouger que son effet. Sans CRN, les courbes « tremblent » à chaque calcul et les comparaisons de branches sont invalides.
- L'implémentation actuelle (`engine/runner.py:40-54`) consomme un flux par hypothèse dans l'ordre trié, puis un flux de bruit séparé. Changer de famille de loi (`normal` → `triangulaire`) change la consommation d'uniformes et donc toute la suite.
- `rng.poisson` consomme un nombre variable d'uniformes : il n'est pas CRN pour un changement de `λ`.
- Le bruit en `(runs, horizon)` en une seule allocation est un risque mémoire pour les grands runs et empêche le calcul par blocs.
- Aucune garantie de préfixe n'est testée aujourd'hui.

## Alternatives

- **Garder l'ordre des clés et un flux unique** : simple, mais un ajout d'hypothèse décale tous les tirages ; impossible de garantir l'indépendance.
- **`SeedSequence.spawn()` par slot** : dépend de l'ordre des appels, donc fragile.
- **scipy.stats** : ajouterait une dépendance lourde au moteur, interdit par le plan.
- **Tirages indexés par run** : correct mais coûteux en mémoire et lent à générer aléatoirement.

## Conséquences

- Les golden tests **changent** : c'est assumé et documenté ; le numéro de version du moteur passe à `0.2.0`.
- `simulate()` n'appelle plus `rng.normal`, `rng.triangular`, `rng.poisson` ni `rng.choice`.
- Un slot inconnu est une erreur de programmation, pas un fallback silencieux.
- Le cache ne doit jamais être partagé entre deux `seed` ou deux horizons.
- L'ADR 0003 reste valide pour : PCG64 local, pas d'état global, `float64`, golden tests, absence de dépendance réseau/UI.

## Vérification

- Tests de préfixe et d'invariance dans `packages/engine/tests/` (phase 03).
- Comparaison des tirages de base avant/après changement de paramètres et de famille.
- Mesure mémoire du cache < 50 Mo et surcoût < 5 % sur `final`.
