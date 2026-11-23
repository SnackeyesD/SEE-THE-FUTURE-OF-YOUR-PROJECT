# Audit du code réel — phase 01

> But : confronter la spec V3 (`docs/V2/V3-COCKPIT.md`) au code de la v2, prouver chaque écart et fixer la phase qui le corrige.
> Méthode : lecture du code, mesure (`npm run bench`, 2026-11-14, commit `1b09972`), recherche exhaustive des symboles concernés. Aucun comportement n'a été modifié.

## 0. Synthèse

| Verdict | Nombre |
|---|---|
| Écarts bloquants pour le cockpit | 5 (C1, C2, C3, C4, C11) |
| Écarts de contrat/protocole | 3 (C5, C12, C10) |
| Décisions de périmètre à trancher | 4 (C6, C7, C8, C9) |
| **Total C1–C12** | **12, tous couverts par une phase** |

Les trois constats les plus structurants :

1. **Les métriques du cockpit n'existent pas** (point mort en mois, trésorerie négative, besoin de financement, bandes mensuelles). Le cockpit ne peut pas être construit avant la phase 02.
2. **L'IPC est mono-thread et bloquant des deux côtés** (Python et Rust). Un calcul bloque les lectures ; l'annulation est impossible. Mesuré : `ping` bloqué 759 ms pendant un calcul.
3. **Le socle de dataviz existe déjà** (`@see/ui/viz`, 8 composants SVG/tokens). La spec qui propose ECharts/uPlot/dockview ferait régresser la refonte UI de la v2.

## 1. Inventaire par module

### 1.1 Moteur — `packages/engine`

| Élément | État réel | Preuve |
|---|---|---|
| API | `simulate(scenario, config, progress)` bloquante, résultat complet en fin de calcul | `engine/runner.py:26-95` |
| Tirages | un `PCG64(seed)` par hypothèse, clés triées ; bruit séparé `SeedSequence([seed, 0x5EED])` | `engine/runner.py:40-54`, `engine/distributions.py:43-73` |
| Lots | `batch_size = 50 000` par défaut ; progression par lot seulement | `engine/scenario.py:150-155`, `engine/runner.py:65-75` |
| Métriques | profit (moyenne, médiane, P10/50/90, perte), revenus, coûts, stock, trésorerie **de fin d'horizon** | `engine/scenario.py:157-189`, `engine/aggregation.py:60-90` |
| Point mort | seuil **théorique mensuel** (`coûts fixes / marge unitaire`), pas un mois observé | `engine/scenario.py:212-217`, `engine/aggregation.py:130-152` |
| Mensuel | uniquement des **moyennes** (revenus, profit, demande, ventes, stock) + probabilité de rupture | `engine/scenario.py:191-208`, `engine/aggregation.py:108-128` |
| Sensibilité | corrélation de Pearson + contribution en corrélation² | `engine/sensitivity.py:8-39` |
| Mémoire | tirages `runs × hypothèses` + bruit `runs × horizon` ; `runs` plafonné à 1 000 000 | `engine/runner.py:42-54`, `engine/scenario.py:151` |
| Reproductibilité | golden tests, mêmes agrégats à graine égale | `packages/engine/tests/test_reproducibility.py`, `tests/golden/` |
| Dépendances | numpy + pydantic uniquement | `packages/engine/pyproject.toml` |

### 1.2 Sidecar — `apps/desktop/src-tauri/sidecar`

| Élément | État réel | Preuve |
|---|---|---|
| Boucle | `serve()` lit une ligne, exécute le handler, écrit la réponse ; **un seul thread** | `sidecar/rpc.py:604-611`, `:626-708` |
| Méthodes simulation | `simulate`, `project.simulate`, notification `simulate.progress` | `sidecar/rpc.py:97-122`, `:540`, `:556` |
| Persistance | `project_service.simulate()` écrit **chaque** run complet (`result_json`) avant de répondre | `sidecar/project_service.py:171-231` |
| Progression | callback `fraction` uniquement, pas d'agrégats partiels | `sidecar/rpc.py:111-118` |
| Annulation | aucune méthode ni jeton | recherche `cancel|CancelToken` : aucune occurrence dans le sidecar |
| Version protocole | `1.7.0` | `sidecar/protocol_models.py:12` |
| Mémoire observée | 67 → 87 Mo (RSS) après calculs | `docs/perf/sidecar.json` |
| Démarrage | 1,44 s à chaud, ~2,6 s à froid | `docs/perf/sidecar.json` + première exécution |

### 1.3 Transport Rust — `apps/desktop/src-tauri`

| Élément | État réel | Preuve |
|---|---|---|
| Attente | `request_with` écrit puis attend la réponse **en tenant le `Mutex` Tauri** | `src/lib.rs:172-184`, `src/sidecar.rs:206-282` |
| Timeout | simulation 600 s; provider/agent 600 s | `src/sidecar.rs:15-18`, `:236-248` |
| Notifications | seule `simulate.progress` est relayée à l'UI ; les autres sont ignorées | `src/sidecar.rs:267-274`, `src/lib.rs:178-183` |
| Requêtes concurrentes | impossible : un `rx` unique, pas de map `id → oneshot` | `src/sidecar.rs:253-281` |
| Redémarrage | les requêtes en attente échouent, mais aucun routage par `runId` | `src/sidecar.rs:253-281` |
| Test de version | assert `1.7.0` codé en dur | `src/sidecar.rs:402` |

### 1.4 Stockage — `packages/storage`

| Élément | État réel | Preuve |
|---|---|---|
| Schéma | 5 migrations ; `LATEST_SCHEMA_VERSION = 5` | `see_storage/migrations/__init__.py:251-258` |
| `scenarios` | `id`, `project_id`, `name`, `model`, `scenario_json`, dates : **ni parent, ni branche, ni version** | `migrations/__init__.py:42-50` |
| `simulation_runs` | `scenario_id`, `engine_version`, `seed`, `runs`, `duration_ms`, `result_json`, pas de qualité/épinglage/statut | `migrations/__init__.py:52-65` |
| Repositories | `ScenarioRepository.add`, `RunRepository.add` sans notion de version ni de brouillon | `see_storage/repositories.py:378-457`, `:458-...` |
| `.simproj` | manifeste avec `schemaVersion = LATEST_SCHEMA_VERSION` | `see_storage/portable.py:63-72`, `:189` |
| Rétention | aucune purge ; les runs s'accumulent | absence de `prune` dans `repositories.py` |

### 1.5 UI — `apps/desktop/src`, `packages/ui`

| Élément | État réel | Preuve |
|---|---|---|
| Dataviz | 8 composants SVG/tokens : `LineChart`, `Histogram`, `BarChart`, `DivergingBars`, `Sparkline`, `Legend`, `scale`, `chart.css` | `packages/ui/src/viz/` |
| État | `useState` locaux dans `App.tsx`, props vers les écrans ; pas de store, pas d'undo | `apps/desktop/src/App.tsx:147-164` |
| Résultats | `ResultsScreen` reçoit `run`, `narration`, callbacks ; lit `run.result` | `apps/desktop/src/screens/ResultsScreen.tsx:20-45` |
| IPC | wrappers `invoke` un par méthode, abonnement `simulation:progress` séparé | `apps/desktop/src/lib/ipc.ts:57-119` |
| Narration | vérification des nombres **côté client uniquement**, par regex | `apps/desktop/src/lib/narration.ts:1-63` |
| Tests UI | aucun test de composant ; pas de Vitest/Testing Library | `apps/desktop/package.json` |
| Tokens | `generate-tokens.mjs` et `ui:check` (couleurs en dur interdites) | `packages/ui/scripts/generate-tokens.mjs`, `scripts/ui-check.mjs` |

### 1.6 Protocole — `packages/protocol`

| Élément | État réel | Preuve |
|---|---|---|
| Version | `1.7.0` | `schema/messages.schema.json:6` |
| Méthodes simulation | `simulate`, `simulate.progress` uniquement | `schema/messages.schema.json:49-56` |
| Types | `SimulationResult`, `SimulateParams` figés sur les agrégats v2 | `schema/messages.schema.json:380-450` |
| Génération | `npm run protocol:generate` produit TS + Python | `packages/protocol/scripts/generate.mjs:158-181` |
| Contrat | `protocol:check` en CI | `package.json`, `.github/workflows/` |
| Absent | `simulation.start`, `simulation.cancel`, `partial`, `surface`, `goalseek`, `trajectories`, `provenance` | recherche dans le schéma : aucune occurrence |

### 1.7 Agent — `packages/agent-core`

| Élément | État réel | Preuve |
|---|---|---|
| Outil simulation | `run_simulation` appelle directement `engine.simulate` en bloquant | `agent_core/tools/simulation.py:27-60` |
| Comparaison | `compare_scenarios` exécute deux simulations séquentiellement | même fichier |
| Contexte | le scénario vient de `context.scenario` ou du payload | `agent_core/tools/simulation.py:44-53` |
| Permissions | outils déclarés et soumis aux permissions existantes | `agent_core/tools/__init__.py`, `agent_core/permissions.py` |
| Limite | aucun accès aux nouveaux agrégats (normal, ils n'existent pas) | — |

### 1.8 Benchmarks

| Élément | État réel | Preuve |
|---|---|---|
| Packs | `cf-bangui-retail-2026.1` et `cg-brazzaville-retail-2026.1`, signature `.sig` | `data/benchmark-packs/packs/` |
| Lookup | service sidecar et outil agent existants | `benchmark_service`, `agent_core/tools/benchmarks.py` |
| Usage cockpit | pas de lookup par paramètre dans l'UI | phase 09 |

## 2. Écarts C1–C12

### C1 — Métriques cockpit absentes

- **Constat** : `Metrics` ne contient ni point mort en mois, ni probabilité de trésorerie négative, ni besoin de financement, ni minimum de trésorerie. `BreakEven` est un seuil théorique, pas un mois observé.
- **Preuve** : `packages/engine/engine/scenario.py:157-189` (champs), `:212-217` (`BreakEven`), `engine/aggregation.py:130-152` (formule).
- **Impact** : les KPI centraux de la spec (§6.1, I2–I4) ne peuvent pas être affichés ; toute UI devrait inventer ou dériver ces chiffres, ce qui viole la règle « le moteur calcule ».
- **Correction** : phase 02 (métriques, CDF de trésorerie, bandes). Définitions figées par l'ADR 0015.

### C2 — Pas de bandes mensuelles P10–P90

- **Constat** : `MonthlyAverages` ne contient que des moyennes et une probabilité de rupture. Aucune valeur par run n'est conservée pour les mois.
- **Preuve** : `packages/engine/engine/scenario.py:191-208`, `engine/aggregation.py:108-128`, `engine/aggregation.py:18-28` (liste des champs sommés).
- **Impact** : impossible de tracer l'éventail P10–P90 mensuel, cœur du cockpit ; un graphique de moyennes suggère une fausse précision.
- **Correction** : phase 02 (échantillon de runs + bandes + histogrammes mensuels), consommé en phase 09/10.

### C3 — Sidecar mono-thread

- **Constat** : `RpcServer.serve()` lit une ligne, exécute le handler, écrit la réponse. Un calcul long bloque toute lecture, donc `ping`, `health` et toute autre requête.
- **Preuve** : `apps/desktop/src-tauri/sidecar/sidecar/rpc.py:604-611`, `:626-708`, handler `simulate` `:97-122`.
- **Mesure** : un `ping` envoyé pendant un calcul 50 000 × 36 mois attend **≈ 700 ms** (`docs/perf/sidecar.json` ; 669–759 ms selon l'exécution).
- **Impact** : aucun flux partiel, aucune annulation, aucune concurrence ; le cockpit ne peut pas être interactif.
- **Correction** : phase 06 (service de runs, worker, writer sérialisé, annulation).

### C4 — Transport Rust bloquant et notifications perdues

- **Constat** : `request_with` envoie la requête puis attend la réponse en boucle sur un canal unique ; la commande Tauri tient le `Mutex` du manageur pendant toute l'attente. Les messages sans `id` ne sont transmis qu'au callback local ; seule `simulate.progress` est relayée à l'UI.
- **Preuve** : `apps/desktop/src-tauri/src/sidecar.rs:206-282`, `:253-274` ; `src/lib.rs:172-184` ; timeout simulation `src/sidecar.rs:15-18`.
- **Impact** : impossible d'envoyer `cancel` pendant un calcul ; les notifications d'autres runs sont jetées ; un calcul long gèle les autres commandes Tauri.
- **Correction** : phase 06 (handle de communication, map `pending`, dispatcher d'événements unique, timeouts courts).

### C5 — Chaque run est persisté, y compris les brouillons à venir

- **Constat** : `project_service.simulate()` écrit systématiquement un `simulation_runs` avec `result_json` complet avant de répondre. Il n'existe aucune notion de qualité de run.
- **Preuve** : `sidecar/project_service.py:206-231`, schéma `migrations/__init__.py:52-65`.
- **Impact** : si le cockpit lance un `draft` à chaque mouvement, la base et le disque explosent ; la latence de réponse inclut SQLite.
- **Correction** : phase 06 (draft jamais persisté) + phase 07 (qualité/épinglage/rétention).

### C6 — Le socle dataviz existe déjà

- **Constat** : `packages/ui/src/viz` fournit lignes, histogrammes, barres, barres divergentes, sparkline, échelle et légende en SVG avec tokens et règles d'accessibilité. Aucune dépendance ECharts/uPlot/dockview.
- **Preuve** : `packages/ui/src/viz/` (8 fichiers), `packages/ui/scripts/generate-tokens.mjs`, `scripts/ui-check.mjs`.
- **Impact** : remplacer ce socle par ECharts/uPlot/dockview imposerait de refaire la refonte, de dupliquer les tokens et de perdre `ui:check`. Le besoin de panneaux redimensionnables ne justifie pas un docking complet.
- **Décision** : ADR 0012 — conserver et étendre `@see/ui/viz`, panneaux redimensionnables maison, presets. Toute exception exige une preuve (bundle, fps, accessibilité) consignée.

### C7 — Budgets incohérents et mesures réelles

- **Constat** : la spec mélange 25×25×300 (187 500 runs) avec un `draft` à 500 runs et une cible « 50 i/s », sans machine de référence. Les mesures réelles de la phase 01 donnent ≈ 10 ms (`draft` 500 × 36), ≈ 63 ms (`final` 5 000 × 36) et ≈ 1,70 s pour un proxy de surface 15×15 × 200.
- **Preuve** : `docs/perf/baseline.md`, `docs/perf/latest.json`, `packages/engine/bench/bench_engine.py`.
- **Impact** : un budget irréaliste bloque les merges ou pousse à tricher (interpolation de chiffres). Un budget trop laxiste masque les régressions.
- **Décision** : budgets du plan §6 confirmés par la mesure ; surface par défaut 15×15 × 200, progressive et annulable ; la grille 25×25×300 reste une option explicite.

### C8 — « ≥ 50 i/s » n'est pas garanti par le seul moteur

- **Constat** : le calcul `draft` prend ~10 ms, mais l'IPC, la sérialisation, le rendu et le throttling s'y ajoutent. Rien ne garantit 50 mises à jour/seconde de bout en bout, surtout sur machine modeste.
- **Preuve** : `docs/perf/baseline.md`, `sidecar/rpc.py:604-611`, `src/lib.rs:172-184`.
- **Impact** : promettre 50 i/s sans mesure produit une UI qui tremble ou des chiffres interpolés.
- **Décision** : viser **30–60 i/s** pendant le glissement, afficher l'état « calcul en cours », ne jamais interpoler de valeurs. Mesure réelle en phase 09 (nécessite l'outillage UI de la phase 08).

### C9 — Recherche d'objectif sur métrique en escalier

- **Constat** : il n'existe aujourd'hui ni `surface()` ni `goal_seek()`. Les métriques Monte Carlo (probabilités, point mort) sont déterministes à graine fixée mais **non lisses** : elles changent par paliers.
- **Preuve** : absence de `surface|goal_seek|nelder` dans le dépôt ; `engine/aggregation.py:60-90` (probabilités) ; `engine/sensitivity.py:8-39` (corrélation, pas de gradient).
- **Impact** : Nelder-Mead ou un gradient échouent sur les plateaux et peuvent annoncer une fausse convergence.
- **Décision** : ADR 0015 + phase 11 — balayage/dichotomie pour un levier monotone, recherche par coordonnées pour plusieurs leviers, budget d'évaluations explicite, message d'infaisabilité honnête.

### C10 — Validation des nombres LLM incomplète

- **Constat** : `verifyNarration` collecte les nombres du payload et extrait les nombres du texte par une regex, en autorisant les arrondis entiers. Il ne gère pas explicitement les milliers avec espace/NBSP, les pourcentages, les plages `a–b`, les unités, ni une tolérance d'arrondi relative. Il s'exécute **côté client uniquement**.
- **Preuve** : `apps/desktop/src/lib/narration.ts:1-63`, usage dans `screens/ResultsScreen.tsx:36-42`.
- **Impact** : un nombre inventé peut passer (ex. « 12 300 » si 12 345 est arrondi, ou l'inverse), et aucun repli déterministe n'existe côté service.
- **Correction** : phase 12 — validateur serveur, normalisation française, tolérance documentée, réparation limitée, repli déterministe hors ligne, ADR 0016.

### C11 — Modèle de données plat : pas de branches ni de versions

- **Constat** : `scenarios` n'a ni `parent_id`, ni `branch_label`, ni `version` ; `simulation_runs` n'a ni qualité, ni épinglage, ni statut, ni référence à une version ; il n'existe pas de table `scenario_versions`.
- **Preuve** : `migrations/__init__.py:42-65`, `:251-258` (5 migrations), `repositories.py:378-457` (scénarios), `:458-...` (runs).
- **Impact** : impossible de dupliquer une branche, de comparer deux versions de façon fiable, d'épingler un run ou d'empêcher la purge d'une référence.
- **Correction** : phase 07 — migration 0006, repositories, export `.simproj` v6, rétention. Sémantique figée par l'ADR 0014.

### C12 — Protocole 1.7.0 sans cycle de vie de run

- **Constat** : le schéma ne connaît que `simulate` (bloquant) et `simulate.progress`. Il n'y a ni `simulation.start`, ni `simulation.cancel`, ni notifications `partial`/`done`/`cancelled`/`error`. Le test Rust assert `1.7.0`.
- **Preuve** : `packages/protocol/schema/messages.schema.json:6`, `:49-56` ; `sidecar/protocol_models.py:12` ; `src/sidecar.rs:402`.
- **Impact** : aucun contrat stable pour le cockpit ; toute implémentation UI serait à refaire au bump.
- **Correction** : phase 06 — protocole `1.10.0`, après `1.8.0` (phase 02) et `1.9.0` (phase 05). Un seul propriétaire du schéma, génération et `protocol:check` obligatoires.

## 3. Écarts secondaires découverts pendant l'audit

| # | Constat | Preuve | Traitement |
|---|---|---|---|
| E1 | `sample_hypothesis` ignore `value` quand `distribution` est présente ; changer la valeur ne change pas le tirage. | `engine/distributions.py:50-53` ; confirmé par le bench (`valueIgnoredWhenDistributionSet`). | Phase 02/03 : sémantique explicite (valeur = mode/centre ou remplacement), tests. |
| E2 | Le bruit mensuel est généré en une fois `(runs, horizon)` ; mémoire proportionnelle. | `engine/runner.py:51-54`. | Phase 03 : blocs et cache. |
| E3 | La progression est par lot de 50 000 ; pour 500 runs, un seul callback utile. | `engine/runner.py:65-75`, mesure 2 callbacks pour 500 runs. | Phase 04 : blocs de 256 et partiels. |
| E4 | `simulate()` ne vérifie pas de jeton d'annulation ; aucun type `SimulationCancelled`. | `engine/runner.py:26-95`, absence dans `engine/errors.py`. | Phase 04. |
| E5 | Le sidecar garde un timeout de 600 s pour la simulation ; une annulation ne peut pas interrompre l'attente Rust. | `src/sidecar.rs:15-18`, `:236-248`. | Phase 06. |
| E6 | `project_service.simulate` crée un scénario si `raw_scenario` est fourni, même pour un simple run. | `sidecar/project_service.py:206-214`. | Phase 06/07 : clarifier création vs exécution. |
| E7 | L'UI n'a pas de tests de composants ni d'infrastructure navigateur. | `apps/desktop/package.json`. | Phase 03 (durcissement : Vitest), 16 (Playwright). |
| E8 | La narration est vérifiée côté client seulement ; le service sidecar n'a pas de validateur. | `apps/desktop/src/lib/narration.ts`, absence dans `sidecar/`. | Phase 12. |
| E9 | Les benchmarks existent mais ne sont pas exposés par paramètre dans l'UI. | `data/benchmark-packs/packs/`, `benchmark_service`. | Phase 09. |
| E10 | Le `Mutex` Tauri est tenu pour toutes les commandes, y compris les lectures rapides. | `src/lib.rs:172-184` et commandes voisines. | Phase 06. |

## 4. Ce que la spec V3 affirme et que l'audit corrige

| Affirmation spec | Réalité | Décision |
|---|---|---|
| « Les métriques existent, il suffit de les afficher » | Faux : point mort en mois, trésorerie négative, financement et bandes manquent. | Phase 02 avant toute UI. |
| « Le streaming est un ajout simple » | Faux : la boucle sidecar est mono-thread et le transport Rust bloque. | Phase 06 complète, la plus risquée. |
| « On peut utiliser ECharts/uPlot/dockview » | Le socle `@see/ui/viz` existe et `ui:check` protège les tokens. | ADR 0012 : garder le socle. |
| « Surface 25×25×300 en interactif » | 187 500 runs ; mesure proxy ≈ 1,70 s pour 45 000 runs, mais la vraie surface CRN reste à mesurer. | Défaut 15×15×200, progressive et annulable. |
| « 50 i/s garantis » | Le moteur le permet (~10 ms), pas nécessairement l'IPC + rendu. | Viser 30–60 i/s, mesurer, ne pas interpoler. |
| « Goal seek par optimisation classique » | Métriques en escalier, pas de gradient fiable. | Coordonnées/dichotomie, budget explicite. |
| « 7 semaines » | Suppose 3 personnes à plein temps, zéro imprévu, signature déjà prête. | 7–8 semaines à 3, 10–12 à 2, 17–21 en solo. |

## 5. Contrats figés par cette phase

- Définitions métier : voir ADR 0015.
- Versionnement : protocole `1.8.0` (02) → `1.9.0` (05) → `1.10.0` (06) → `1.11.0` (10) → `1.12.0` (11) → `1.13.0` (12) → `1.14.0` (13) ; scénario `1.0.0` → `1.1.0` (05) ; base migration `0006` (07).
- Budgets : voir `docs/perf/baseline.md` §3.
- Dataviz : `@see/ui/viz` conservé (ADR 0012).
- 3D : Three.js + `@react-three/fiber`, lazy, repli heatmap (ADR 0013).
- État : Zustand + commandes inversibles ; résultats non annulables (ADR 0014).
- Explication : payload de provenance + validateur serveur + repli déterministe (ADR 0016).
- CRN : banque de tirages par slot et bloc, préfixe testé (ADR 0010).
- IPC : worker, writer unique, dispatcher Rust, `runId`/`seq` (ADR 0011).

## 6. Reproductibilité de l'audit

```bash
npm run bench
npm run protocol:check
git rev-parse --short HEAD
```

Les preuves de ligne peuvent se décaler après les phases suivantes ; ce document décrit l'état au commit `1b09972`. Toute divergence ultérieure doit être expliquée dans l'ADR ou le README de la phase concernée.
