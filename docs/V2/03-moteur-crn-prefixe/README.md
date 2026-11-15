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

- [x] `packages/engine/engine/draws.py` : `DrawBank`, `DrawSlot`, génération par blocs.
- [x] `distributions.py` : échantillonnage par inversion / transformation à partir de `U`/`Z`.
- [x] `runner.py` : utilise la banque, plus aucun `rng.normal/triangular/...`.
- [x] Cache borné, clé stable, invalidation documentée.
- [x] Tests de préfixe, d'invariance et de mémoire.
- [x] Golden vérifiés (inchangés, scénario déterministe) ; `__version__` bumpée (0.2.0).
- [x] Documentation dans `packages/engine/README.md`.

## 4. Tâches détaillées

### Lot A — Banque de tirages

- [x] Définir les tailles de bloc documentées : `BLOCK_SIZE = 1024` (slots vectoriels) et `SCALAR_BLOCK_SIZE = 2048` (slots scalaires). Écart assumé par rapport aux 256 initiaux, justifié par la mesure (voir §8).
- [x] Pour chaque slot, deux flux de base indépendants :
  - `u` : uniformes `U(0,1)` ;
  - `z` : normales standard `Z`.
- [x] Dériver le générateur du couple `(slot, bloc, flux)` par :
  ```python
  seq = np.random.SeedSequence([seed, slot_id, block_index, stream])
  rng = np.random.Generator(np.random.PCG64(seq))
  ```
  où `slot_id` est un entier 64 bits stable dérivé du nom du slot (BLAKE2b), **pas** l'index d'insertion, et `stream` vaut `0` (`U`) ou `1` (`Z`). Le quatrième mot garantit que générer un flux seul ne décale pas l'autre.
- [x] Générer les flux **à la demande** par slot ; une loi ne demande que le flux qu'elle consomme (`distribution_streams()`). Le cache permet l'accès aléatoire.
- [x] Exposer `bank.block(slot, index) -> tuple[np.ndarray, np.ndarray]`, `bank.take(slot, n)` et `bank.take_range(...)`, avec sélection des flux (`uniform=`, `normal=`) pour ne pas générer l'inutile.
- [x] Prévoir `invalidate_structure()` appelé quand la liste des slots change ; documenter que les slots existants gardent leurs tirages.

### Lot B — Slots

- [x] Convention de nommage :
  - `hyp:<clé>` pour chaque hypothèse résolue ;
  - `noise` pour le bruit mensuel : un `Z` de forme `(block, horizon)` ;
  - `event:<id>:active` et `event:<id>:magnitude` (phase 05) ;
  - réservé : `event:<id>:magnitude_z` si la loi est normale.
- [x] Trier les slots par nom pour la génération, mais **la génération d'un slot ne dépend pas des autres**.
- [x] Le bruit mensuel est généré par blocs de 1024 runs : `Z` de forme `(block, horizon)`, jamais `(runs, horizon)` en une fois. Le lot courant est concaténé au maximum, pas l'horizon complet.
- [x] Cache : `dict[(slot, block)] -> {flux: array}`, LRU de 16 blocs, une entrée par bloc.
- [x] Un cache plein ne doit jamais changer les valeurs, seulement provoquer une régénération déterministe.

### Lot C — Transformations sans aléa supplémentaire

- [x] `normal` : `moyenne + écart_type × Z`.
- [x] `lognormal` : `exp(mu + sigma × Z)`.
- [x] `uniform` : `low + U × (high - low)`.
- [x] `triangulaire` : inversion de la CDF en forme fermée :
  ```python
  # a=low, b=mode, c=high, U∈[0,1)
  seuil = (b - a) / (c - a)
  x = np.where(U < seuil,
               a + np.sqrt(U * (c - a) * (b - a)),
               c - np.sqrt((1 - U) * (c - a) * (c - b)))
  ```
  Gérer `a == b` et `b == c` sans division par zéro.
- [x] `empirical` : CDF cumulée des poids, `np.searchsorted(cdf, U)`.
- [x] `poisson` : **inversion exacte** de la CDF pour un λ scalaire. La table `P(X ≤ k)` est construite en espace logarithmique puis cumulée, mise en cache par λ, et consommée par `np.searchsorted`. Au-delà de `POISSON_EXACT_MAX = 50 000`, approximation normale `N(λ, √λ)` **explicitement signalée** dans `SimulationResult.approximations`.
- [x] Aucune fonction `rng.normal`, `rng.triangular`, `rng.poisson`, `rng.choice` ne subsiste dans le chemin d'échantillonnage.
- [x] Conserver les bornes `min/max` et le clip actuels, appliqués **après** transformation.

### Lot D — Runner

- [x] Remplacer la génération `samples[key] = sample_hypothesis(..., rng, runs)` par un tirage banque + `sample_hypothesis(hypothesis, U, Z, bounds)`, en ne demandant que le flux utile.
- [x] Remplacer `noise_rng.standard_normal((runs, horizon))` par `bank.take_range("noise", start, end, uniform=False)` à chaque lot.
- [x] Garder l'ordre de résolution `model.resolve(scenario)` mais ne plus dépendre de l'ordre du dict pour les tirages.
- [x] Vérifier que le calcul par lots ne rappelle pas la banque avec des tailles différentes : toujours `n` total pour les hypothèses, puis slicing par lot ; le bruit est pris par plage de lot.

### Lot E — Tests

- [x] **Préfixe** : `simulate(n=1000)` et `simulate(n=250)` → les 250 premiers profits et paramètres tirés sont identiques (comparer les tableaux, pas seulement les agrégats).
- [x] **Préfixe inter-blocs** : n = 250, 256, 257, 500, 1000, plus 1023/1024/1025 et 2047/2048.
- [x] **Invariance de paramètres** : modifier `mean/std` d'une normale ou `low/mode/high` d'une triangulaire ne change ni `U` ni `Z` du slot.
- [x] **Invariance de famille** : passer de `normal` à `triangular` conserve `U` et `Z` du slot ; seules les valeurs transformées changent.
- [x] **Indépendance de l'ordre** : réordonner `scenario.assumptions` ne change aucun tirage.
- [x] **Indépendance d'ajout** : ajouter une hypothèse ne change pas les tirages des hypothèses existantes.
- [x] **Loi** : moyennes/variances conformes (test de propriétés, tolérances statistiques).
- [x] **Poisson** : comparaison à une CDF de référence pour λ ∈ {1, 5, 30}.
- [x] **Mémoire** : cache borné (16 blocs) et testé.
- [x] **Golden** : vérifié inchangé. Le scénario golden est déterministe (`demand_cv = 0`, aucune distribution), donc le changement de méthode ne modifie aucun agrégat. Le diff de paramètres tirés n'existe pas ; il est expliqué dans l'ADR 0010.

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

- [x] Tous les tests de préfixe passent, y compris 250/256/257 et les frontières 1024/2048.
- [x] Changer un paramètre ne modifie pas les tirages de base.
- [x] Ajouter une hypothèse ou un événement ne modifie pas les tirages existants.
- [x] Le bruit mensuel est généré par blocs et la mémoire reste bornée.
- [x] Aucun appel aux distributions de `numpy.random.Generator` dans le chemin de tirage.
- [x] Golden et documentation à jour.

## 8. Performance

- Surcoût de la banque < 5 % sur `final` 5 000 × 36 — **mesuré +3,0 %** (77,6 ms contre 75,3 ms pour la phase 02, `npm run bench` sur la machine de référence).
- `draft` 500 × 36 : ≤ 20 ms sur poste dev (hors agrégats) — **mesuré ≈ 14,6 ms**.
- Cache : ≤ 64 blocs, mémoire < 50 Mo — **16 blocs, < 10 Mio** pour le bruit à 36 mois.
- Aucune allocation `runs × horizon × nombre_de_slots`.

Détail de la mesure (médianes, `npm run bench`, machine de référence) :

| Mesure | Phase 02 | Phase 03 | Écart | Budget |
|---|---|---|---|---|
| `draft` 500 × 36 | 12,9 ms | **14,4 ms** | +11 % | ≤ 50 ms (cible dev ≤ 20 ms) |
| `final` 5 000 × 36 | 75,3 ms | **77,6 ms** | +3,0 % | ≤ 400 ms, surcoût banc < 5 % |
| `large` 20 000 × 36 | 242,9 ms | **252,1 ms** | +3,8 % | — |
| Payload `final` | 28,0 Kio | **28,0 Kio** | 0 % | < 100 Kio |

## 9. Risques

| Risque | Mitigation |
|---|---|
| Préfixe faux à cause du cache | Tests aux frontières de blocs, cache pur |
| Collision d'identifiants de slots | BLAKE2b 64 bits, test de noms connus |
| Loi déformée par une mauvaise inversion | Tests statistiques + CDF de référence |
| Golden massif | Diff justifié, version moteur bumpée |
| Complexité pour un intermédiaire | Module isolé, revue senior, tests avant intégration |

## 10. Definition of Done

- [x] `DrawBank` documentée et testée.
- [x] `simulate()` n'utilise plus que des tirages de base.
- [x] Préfixe, invariance et mémoire prouvés par les tests.
- [x] ADR 0010 mis à jour avec l'implémentation réelle.
- [x] Golden vérifiés : inchangés, car le scénario est déterministe ; le cas avec distributions est expliqué dans l'ADR.

## 11. Mise en œuvre — écarts assumés

L'implémentation suit le plan, avec quatre écarts documentés et mesurés :

1. **Tailles de bloc** : `1024` runs pour le bruit (mémoire bornée par lot) et `2048` pour
   les slots scalaires (déjà matérialisés en entier par le runner). Les blocs de `256` de
   la rédaction initiale multipliaient les générateurs et les concaténations ; le surcoût
   sur `final` passait d'environ +3 % à environ +7,5 %.
2. **Flux paresseux et indépendants** : l'entropie du générateur devient
   `SeedSequence([seed, slot_id, block_index, stream])`, avec `stream = 0` pour `U` et
   `1` pour `Z`. Le runner ne demande que le flux consommé par la loi
   (`distribution_streams()`), ce qui évite de générer des uniformes inutiles pour les
   normales et des normales inutiles pour les triangulaires.
3. **Poisson exact jusqu'à λ = 50 000** : table en espace logarithmique, stable pour les
   grands λ, mise en cache. Au-delà, approximation normale signalée par
   `SimulationResult.approximations = ["poisson_normal"]` (champ optionnel, protocole
   `1.8.0` inchangé).
4. **Cache de 16 blocs** au lieu de 64 : à 1024 runs × 36 mois, un bloc de bruit pèse
   environ 576 Kio, soit moins de 10 Mio pour l'ensemble du cache.

Fichiers principaux :

- `packages/engine/engine/draws.py` — `DrawBank`, `DrawSlot`, blocs, flux, cache ;
- `packages/engine/engine/distributions.py` — transformations et routage des flux ;
- `packages/engine/engine/runner.py` — intégration, bruit par lot, approximations ;
- `packages/engine/engine/scenario.py` — champ optionnel `approximations` ;
- `packages/engine/tests/test_draws.py`, `test_crn.py`, `test_distributions.py`.

Commandes de validation : `npm run engine:test` (96 tests), `npm run engine:lint`,
`npm run protocol:check`, `npm run bench`.

## 12. Durcissement après revue senior

La revue a demandé de rendre explicites les garde-fous qui étaient implicites :

| Point | Mise en œuvre |
|---|---|
| Couverture CI multi-OS | Jobs `web`, `python` et `rust` en matrice `ubuntu-latest`, `macos-latest`, `windows-latest`, avec `fail-fast: false`. |
| Tests Python complets | `providers`, `agent-core`, `benchmarks` et `sandbox` sont sync, lint et testés en CI, en plus de `engine`, `storage` et `sidecar`. |
| Tests UI | Vitest + Testing Library + jsdom dans `apps/desktop` ; parcours couverts : validation et lancement de simulation, résultats et contrôle de narration, ouverture d'un projet et passage simulation → résultats, remontée d'erreur moteur. |
| Protocole | `npm run protocol:check` tourne dans les jobs web **et** Python ; `CLAUDE.md` rappelle que tout changement de schéma exige `protocol:generate` et le commit des fichiers générés. |
| Erreurs sidecar | `simulate()` journalise le traceback complet via `logger.exception` et renvoie `INTERNAL_ERROR` avec un message actionnable, sans exposer le détail interne. Un test vérifie le code, le message et la présence du traceback. |
| Notifications | `simulate.progress` quitte `MethodName` et rejoint `NotificationName` ; un commentaire dans `rpc.py` rappelle qu'il s'agit d'une notification JSON-RPC sans `id`. |
| Shell Rust | `cargo test` tourne sur les trois OS avec la toolchain stable ; les dépendances système Tauri sont installées sur Linux. Vérifié localement sur Linux : 5 tests passent (`keychain`, `sidecar`). Windows reste couvert par le job CI, mais ne peut pas être exécuté sur la machine de développement Linux. |

Commandes ajoutées : `npm test` (protocole + Vitest), `npm run test -w @see/desktop`.
