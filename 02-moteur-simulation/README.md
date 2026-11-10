# Phase 02 — Moteur de simulation

> **Objectif** : construire `packages/engine`, le moteur Monte Carlo déterministe et rapide qui produit **tous** les chiffres du produit. Le LLM ne calcule jamais à sa place.

**Références** : `ARCHITECTURE-DESKTOP.md` §1 (« le moteur calcule »), §13, §14 (étape 1).

---

## 1. Contexte et dépendances

- **Dépend de** : phase 01 (sidecar, protocole, CI).
- **Débloque** : phases 03, 05, 06, 08, 09.
- **Contrainte** : réutiliser ce package tel quel entre desktop et éventuel cloud/web.

## 2. Objectifs

1. Un modèle de simulation **`retail_depot`** réaliste et paramétrable.
2. Un runner Monte Carlo vectorisé (numpy), reproductible par graine.
3. Des sorties agrégées stables : P10/P50/P90, moyenne, histogrammes, seuil de rentabilité, sensibilité.
4. Un schéma d'entrée/sortie versionné et validé.
5. Une performance compatible avec l'interactivité desktop.
6. Une base de tests qui empêche toute dérive silencieuse.

## 3. Périmètre

**Inclus**
- Primitives de distributions et génération aléatoire.
- Modèle de scénario (hypothèses, paramètres, incertitudes).
- Moteur `retail_depot`.
- Agrégation et export JSON/Parquet.
- CLI de test et de benchmark.
- Tests unitaires, de propriétés, golden, performance.

**Exclu**
- Appels LLM (phase 04/05).
- UI et graphiques (phase 06).
- Benchmarks de référence (phase 08) — mais prévoir l'interface d'injection.

## 4. Livrables

- [ ] `packages/engine/` complet, publiable, sans dépendance à Tauri.
- [ ] Schémas `Scenario`, `Hypothesis`, `SimulationConfig`, `SimulationResult` (Pydantic).
- [ ] Runner `simulate(scenario, config) -> SimulationResult`.
- [ ] Modèle `retail_depot`.
- [ ] CLI `python -m engine run --scenario ... --runs ... --seed ...`.
- [ ] Jeu de tests (unitaires, propriétés, golden, perf).
- [ ] Documentation : modèle mathématique, hypothèses, limites.
- [ ] ADR sur la reproductibilité et le choix numpy.

## 5. Tâches détaillées

### Lot A — Primitives
- [ ] Générateur `PCG64` encapsulé ; une graine → une séquence reproductible.
- [ ] Distributions : normale, log-normale, triangulaire, uniforme, Poisson, discrète empirique.
- [ ] Échantillonnage vectorisé, pas de boucle Python sur les runs.
- [ ] Validation : bornes, positivité, paramètres cohérents.

### Lot B — Schéma de scénario
- [ ] `Scenario` : identité, devise (FCFA par défaut), horizon, unités.
- [ ] `Hypothesis` : valeur, distribution, source, confiance, min/max.
- [ ] `SimulationConfig` : nombre de runs, graine, taille de lot, options.
- [ ] Versionner le schéma (`schema_version`) et prévoir la migration.

### Lot C — Modèle `retail_depot`
- [ ] Coûts fixes, coûts variables, marge unitaire, volume, saisonnalité.
- [ ] Incertitudes sur prix, demande, coûts, taux de perte.
- [ ] Règles métier du dépôt (stock, réapprovisionnement, ruptures).
- [ ] Paramètres injectables depuis les hypothèses du brief.
- [ ] Documentation des formules et des hypothèses simplificatrices.

### Lot D — Runner et agrégation
- [ ] Exécution par lots (chunking) pour borner la mémoire.
- [ ] Notifications de progression (0–100 %) via le protocole.
- [ ] Agrégats : moyenne, médiane, P10/P50/P90, min/max, écart-type.
- [ ] Histogramme (bins stables) et courbe de rentabilité cumulée.
- [ ] Analyse de sensibilité : contribution des hypothèses à la variance.
- [ ] Résultat déterministe à graine fixée.

### Lot E — Sorties
- [ ] Contrat JSON stable pour l'IPC (mêmes champs que le protocole).
- [ ] Écriture Parquet/JSON compressé pour les runs volumineux.
- [ ] Métadonnées : version du moteur, graine, durée, configuration.

### Lot F — Tests et performance
- [ ] Golden tests : scénarios de référence + hash/ valeurs attendues.
- [ ] Tests de propriétés : bornes, monotonie, conservation des quantités.
- [ ] Tests de reproductibilité : même graine = mêmes agrégats.
- [ ] Tests de non-régression sur le schéma.
- [ ] Benchmark : objectif indicatif **< 2 s pour 100 000 runs** sur un scénario standard.
- [ ] Budget mémoire documenté.

### Lot G — Contenu métier
- [ ] Définir les paramètres par défaut prudents (pas de fausse précision).
- [ ] Préparer les emplacements d'injection des benchmarks (phase 08).
- [ ] Relecture métier des formules par une personne du domaine.

## 6. Décisions techniques

| Sujet | Choix |
|---|---|
| Langage | Python 3.11+, **numpy uniquement** |
| Reproductibilité | `numpy.random.Generator(PCG64(seed))`, dtype fixés |
| Vectorisation | opérations numpy par lots, pas de `for` sur les runs |
| Stockage des runs | agrégats en mémoire ; détail en Parquet si demandé |
| Versionnage numpy | épinglé ; golden tests rejoués à chaque montée de version |

## 7. Arborescence concernée

```
packages/engine/
├── engine/
│   ├── __init__.py
│   ├── distributions.py
│   ├── scenario.py         # schémas Pydantic
│   ├── runner.py
│   ├── aggregation.py
│   ├── sensitivity.py
│   ├── models/
│   │   └── retail_depot.py
│   └── cli.py
├── tests/
│   ├── test_distributions.py
│   ├── test_runner.py
│   ├── test_retail_depot.py
│   ├── test_reproducibility.py
│   └── golden/
└── README.md
```

## 8. Critères d'acceptation

- [ ] Même scénario + même graine = résultats identiques (bit à bit sur les agrégats, dans la même version de numpy).
- [ ] 100 000 runs en moins de 2 s sur la machine de référence.
- [ ] Aucune dépendance à Tauri, au réseau ou à un fournisseur IA.
- [ ] Schéma validé ; une entrée invalide produit une erreur claire, pas un résultat faux.
- [ ] Les sorties couvrent : rentabilité, distribution du profit, seuil de rentabilité, sensibilité.
- [ ] Les golden tests échouent si les formules changent sans mise à jour assumée.
- [ ] Documentation mathématique relue.

## 9. Tests et qualité

- Couverture cible : > 90 % sur le cœur.
- Tests de propriétés (`hypothesis` ou équivalent).
- Test de stabilité des percentiles sur plusieurs graines.
- Test de performance en CI (avec tolérance machine, non bloquant au début).
- Test d'intégration : appel depuis le sidecar (phase 01) et retour JSON.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Modèle jugé irréaliste | Relecture métier, paramètres par défaut prudents, hypothèses affichées |
| Résultats non reproductibles entre OS | Dtype fixés, numpy épinglé, éviter les opérations non déterministes |
| Lenteur sur PC modestes | Vectorisation, chunking, budget de performance testé |
| Fausse précision | Afficher les intervalles et la confiance, pas un chiffre unique |
| Dérive silencieuse des formules | Golden tests + revue de tout changement |

## 11. Estimation

**2 à 3 semaines**, dont une part significative pour la validation métier du modèle.

## 12. Definition of Done

- [ ] Moteur utilisable en CLI et via le sidecar.
- [ ] Golden tests et tests de reproductibilité verts.
- [ ] Documentation des formules et limites.
- [ ] ADR reproductibilité écrit.
- [ ] Résultats validés par une relecture métier.
