# Phase 03 — Tirages communs & propriété de préfixe

> **Objectif** : quand l'utilisateur bouge un curseur, **seul l'effet du paramètre change**. Les courbes ne tremblent pas, les comparaisons sont valides, et les `n` premiers runs d'un calcul à `N` runs sont identiques à ceux d'un calcul à `n` runs.

**Références** : `V3-COCKPIT.md` §3.1, §11 ; ADR 0003 (existant), ADR 0010 (phase 01).
**Dépend de** : phase 02 (schéma et agrégats stabilisés).
**Débloque** : 04, 05, 11, 12.
**Profil** : senior Python (numérique) ; 5–6 jours. **Revue senior obligatoire.**

---

## 1. Contexte

Le moteur actuel consomme un flux `PCG64(seed)` par hypothèse dans l'ordre trié, puis un flux séparé pour le bruit. Cela donne déjà une stabilité partielle quand on change les paramètres d'une loi (mêmes uniformes transformés), mais :

- changer de **famille** de loi change la méthode de tirage et donc la séquence ;
- le bruit mensuel est généré en une fois (`runs × horizon`) : la mémoire explose pour de grands runs ;
- il n'y a **aucune garantie testée** de préfixe quand `runs` change ;
- ajouter une hypothèse ou un événement peut décaler les tirages des autres ;
- `rng.poisson` consomme un nombre variable d'uniformes, donc n'est pas CRN pour un changement de λ.

La V3 a besoin d'une **banque de tirages** explicite et testée.

## 2. Périmètre

**Inclus**

- Génération de tirages de base `U(0,1)` et `Z` par **slot** et par **bloc**.
- Transformation des tirages en valeurs selon la distribution, sans consommer d'autre aléa.
- Propriété de préfixe, indépendance de l'ordre des clés, indépendance de l'ajout d'un slot.
- Cache borné des blocs.
- Tests de propriétés et golden mis à jour.

**Exclu**

- Progression, annulation (phase 04).
- Événements (phase 05) — mais les slots sont prévus pour eux.
- Transport (phase 06).

## 3. Livrables

- [ ] `packages/engine/engine/draws.py` : `DrawBank`, `DrawSlot`, génération par blocs.
- [ ] `distributions.py` : échantillonnage par inversion / transformation à partir de `U`/`Z`.
- [ ] `runner.py` : utilise la banque, plus aucun `rng.normal/triangular/...`.
- [ ] Cache borné, clé stable, invalidation documentée.
- [ ] Tests de préfixe, d'invariance et de mémoire.
- [ ] Golden régénérés et versionnés ; `__version__` bumpée (0.2.0).
- [ ] Documentation dans `packages/engine/README.md`.

## 4. Tâches détaillées

### Lot A — Banque de tirages

- [ ] Définir `BLOCK_SIZE = 256` (constante, documentée).
- [ ] Pour chaque slot, générer deux tableaux par bloc :
  - `u` : uniformes `U(0,1)` ;
  - `z` : normales standard `Z`.
- [ ] Dériver le générateur du couple `(slot, bloc)` par :
  ```python
  seq = np.random.SeedSequence([seed, slot_id, block_index])
  rng = np.random.Generator(np.random.PCG64(seq))
  ```
  où `slot_id` est un entier 64 bits stable dérivé du nom du slot (BLAKE2b), **pas** l'index d'insertion.
- [ ] Générer **tous les slots** pour un bloc avant de le mettre en cache, ou à la demande par slot ; le cache doit permettre l'accès aléatoire.
- [ ] Exposer `bank.block(slot, index) -> tuple[np.ndarray, np.ndarray]` et `bank.take(slot, n)` qui concatène les blocs `0..ceil(n/B)-1` puis tronque à `n`.
- [ ] Prévoir `invalidate_structure()` appelé quand la liste des slots change ; documenter que les slots existants gardent leurs tirages.

### Lot B — Slots

- [ ] Convention de nommage :
  - `hyp:<clé>` pour chaque hypothèse résolue ;
  - `noise` pour le bruit mensuel : un `Z` de forme `(runs, horizon)` ;
  - `event:<id>:active` et `event:<id>:magnitude` (phase 05) ;
  - réservé : `event:<id>:magnitude_z` si la loi est normale.
- [ ] Trier les slots par nom pour la génération, mais **la génération d'un slot ne dépend pas des autres**.
- [ ] Le bruit mensuel est généré par blocs de runs : `Z` de forme `(block, horizon)`, jamais `(runs, horizon)` en une fois.
- [ ] Cache : `dict[(seed, horizon, slot, block)] -> arrays`, LRU de taille bornée (ex. 64 blocs), compteur de mémoire.
- [ ] Un cache plein ne doit jamais changer les valeurs, seulement provoquer une régénération déterministe.

### Lot C — Transformations sans aléa supplémentaire

- [ ] `normal` : `moyenne + écart_type × Z`.
- [ ] `lognormal` : `exp(mu + sigma × Z)`.
- [ ] `uniform` : `low + U × (high - low)`.
- [ ] `triangulaire` : inversion de la CDF en forme fermée :
  ```python
  # a=low, b=mode, c=high, U∈[0,1)
  seuil = (b - a) / (c - a)
  x = np.where(U < seuil,
               a + np.sqrt(U * (c - a) * (b - a)),
               c - np.sqrt((1 - U) * (c - a) * (c - b)))
  ```
  Gérer `a == b` et `b == c` sans division par zéro.
- [ ] `empirical` : CDF cumulée des poids, `np.searchsorted(cdf, U)`.
- [ ] `poisson` : **inversion exacte** de la CDF pour un λ scalaire. Construire la table `P(X ≤ k)` par récurrence jusqu'à `1 - 1e-12`, puis `np.searchsorted`. Si la table dépasserait une taille raisonnable (λ très grand), utiliser une approximation normale **explicitement signalée** dans les métadonnées du résultat.
- [ ] Aucune fonction `rng.normal`, `rng.triangular`, `rng.poisson`, `rng.choice` ne doit subsister dans le chemin d'échantillonnage.
- [ ] Conserver les bornes `min/max` et le clip actuels, appliqués **après** transformation.

### Lot D — Runner

- [ ] Remplacer la génération `samples[key] = sample_hypothesis(..., rng, runs)` par `samples_from_draws(spec, bank, runs, slot)`.
- [ ] Remplacer `noise_rng.standard_normal((runs, horizon))` par `bank.take("noise", runs)`.
- [ ] Garder l'ordre de résolution `model.resolve(scenario)` mais ne plus dépendre de l'ordre du dict pour les tirages.
- [ ] Vérifier que le calcul par lots ne rappelle pas la banque avec des tailles différentes : toujours `n` total, puis slicing par lot.

### Lot E — Tests

- [ ] **Préfixe** : `simulate(n=1000)` et `simulate(n=250)` → les 250 premiers profits et paramètres tirés sont identiques (comparer les tableaux, pas seulement les agrégats).
- [ ] **Préfixe inter-blocs** : n = 250, 256, 257, 500, 1000.
- [ ] **Invariance de paramètres** : modifier `mean/std` d'une normale ou `low/mode/high` d'une triangulaire ne change ni `U` ni `Z` du slot.
- [ ] **Invariance de famille** : passer de `normal` à `triangular` conserve `U` et `Z` du slot ; seules les valeurs transformées changent.
- [ ] **Indépendance de l'ordre** : réordonner `scenario.assumptions` ne change aucun tirage.
- [ ] **Indépendance d'ajout** : ajouter une hypothèse ne change pas les tirages des hypothèses existantes.
- [ ] **Loi** : moyennes/variances conformes (test de propriétés, tolérances statistiques).
- [ ] **Poisson** : comparaison à une CDF de référence pour λ ∈ {1, 5, 30}.
- [ ] **Mémoire** : mesurer le cache et le comparer au plafond.
- [ ] **Golden** : régénérer et expliquer le diff (le changement de méthode est assumé).

## 5. Contrats

```python
@dataclass(frozen=True)
class DrawSlot:
    name: str          # "hyp:unit_price", "noise", "event:ev1:active"
    id: int            # 64 bits stable, dérivé du name


class DrawBank:
    def __init__(self, seed: int, horizon: int, block_size: int = 256) -> None: ...
    def register(self, slot: str) -> DrawSlot: ...
    def take(self, slot: str, runs: int) -> tuple[np.ndarray, np.ndarray]: ...
    def clear(self) -> None: ...
```

Invariants :

1. `take(slot, n)[0][:k] == take(slot, k)[0]` pour tout `k ≤ n`.
2. Les tableaux d'un slot ne dépendent ni de l'ordre d'enregistrement, ni des autres slots.
3. Un changement de paramètres de loi ne modifie ni `U` ni `Z`.
4. Le cache ne change jamais les valeurs.

## 6. Pièges

- **Ne pas utiliser `SeedSequence.spawn()` par slot dans un ordre variable** : l'ordre d'appel changerait les enfants. Utiliser un identifiant stable.
- **Ne pas dériver `slot_id` de l'index** : ajouter une hypothèse décalerait tout.
- **Ne pas générer le bruit en `(runs, horizon)`** : mémoire et préfixe.
- **Ne pas utiliser `np.random.default_rng` global** : toujours des générateurs locaux.
- **Triangulaire** : les formules numpy gèrent des cas limites ; les réimplémenter explicitement et les tester.
- **Poisson** : ne pas accepter silencieusement une approximation ; la signaler dans `SimulationResult`.
- **Golden** : un diff est normal ici, mais il doit être justifié, pas masqué.

## 7. Critères d'acceptation

- [ ] Tous les tests de préfixe passent, y compris 250/256/257.
- [ ] Changer un paramètre ne modifie pas les tirages de base.
- [ ] Ajouter une hypothèse ou un événement ne modifie pas les tirages existants.
- [ ] Le bruit mensuel est généré par blocs et la mémoire reste bornée.
- [ ] Aucun appel aux distributions de `numpy.random.Generator` dans le chemin de tirage.
- [ ] Golden et documentation à jour.

## 8. Performance

- Surcoût de la banque < 5 % sur `final` 5 000 × 36.
- `draft` 500 × 36 : ≤ 20 ms sur poste dev (hors agrégats).
- Cache : ≤ 64 blocs, mémoire < 50 Mo.
- Aucune allocation `runs × horizon × nombre_de_slots`.

## 9. Risques

| Risque | Mitigation |
|---|---|
| Préfixe faux à cause du cache | Tests aux frontières de blocs, cache pur |
| Collision d'identifiants de slots | BLAKE2b 64 bits, test de noms connus |
| Loi déformée par une mauvaise inversion | Tests statistiques + CDF de référence |
| Golden massif | Diff justifié, version moteur bumpée |
| Complexité pour un intermédiaire | Module isolé, revue senior, tests avant intégration |

## 10. Definition of Done

- [ ] `DrawBank` documentée et testée.
- [ ] `simulate()` n'utilise plus que des tirages de base.
- [ ] Préfixe, invariance et mémoire prouvés par les tests.
- [ ] ADR 0010 mis à jour avec l'implémentation réelle.
- [ ] Golden régénérés et revus.
