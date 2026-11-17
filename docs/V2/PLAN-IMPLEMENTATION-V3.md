# Plan d'implémentation V3 — Cockpit de simulation

> Document maître. Il transforme `V3-COCKPIT.md` en **16 phases livrables**, après audit du code réel de la v2.
> Chaque phase a son dossier et son `README.md` avec contrats, lots de tâches, tests et critères d'acceptation.

**Public** : développeur senior ou intermédiaire. Les phases indiquent le profil recommandé et les points qui exigent une revue senior.

---

## 0. Objet et principes

La V3 transforme l'écran de résultats en **cockpit interactif** : on bouge une hypothèse, la simulation se recalcule, les courbes réagissent sans trembler, et l'utilisateur peut ajouter des événements, chercher un objectif, comparer des branches et expliquer chaque chiffre.

Principes inchangés :

- **le LLM comprend et explique, le moteur calcule** — aucun chiffre de simulation ne naît dans l'UI ni dans le LLM ;
- **honnêteté de l'incertitude** — fourchettes, graine visible, pas d'animation qui suggère une fausse précision ;
- **reproductibilité** — même graine + même structure = mêmes résultats ;
- **local-first** — le cloud n'est jamais requis pour simuler ;
- **dégradation élégante** — la 3D est un complément, jamais l'unique voie.

Hypothèses de travail :

1. Cible principale Windows, puis Linux (WebKitGTK), puis macOS.
2. Équipe de référence : **3 personnes à temps plein** (1 moteur/sidecar senior, 1 UI senior, 1 UI/storage intermédiaire) + 0,5 produit/design. En solo, le plan reste valable mais prend **17 à 21 semaines**.
3. Les budgets de performance sont mesurés sur une machine modeste définie en phase 01, pas sur le poste de développement.
4. Les phases sont séquentielles par dépendance, mais plusieurs peuvent tourner en parallèle (voir §3).

---

## 1. Ce que l'audit change par rapport à `V3-COCKPIT.md`

L'audit du dépôt (moteur, protocole, sidecar, transport Rust, stockage, UI) impose douze corrections. Elles sont intégrées dans les phases ; la spec d'origine reste la référence produit.

| # | Constat réel | Conséquence | Phase |
|---|---|---|---|
| C1 | `Metrics` ne contient ni point mort en mois, ni probabilité de trésorerie négative, ni besoin de financement. `BreakEven` est un seuil mensuel théorique, pas un mois observé. | Ajouter les métriques cockpit avant toute UI. | 02 |
| C2 | `MonthlyAverages` ne contient que des **moyennes** : impossible de tracer un éventail P10–P90 mensuel. | Stocker un échantillon de runs et calculer les bandes mensuelles. | 02 |
| C3 | `rpc.py` est mono-thread : `serve()` lit une ligne, exécute le handler, écrit la réponse. Un calcul bloque toute lecture. | Refondre le sidecar en service de runs + writer sérialisé. | 06 |
| C4 | Le transport Rust (`sidecar.rs`) est bloquant et garde un `Mutex` pendant l'attente ; il jette les notifications non liées à la requête courante. | Refondre le dispatcher Rust avant toute interaction live. | 06 |
| C5 | `project_service.simulate()` persiste **chaque** run en SQLite (`result_json` complet). | Les runs `draft` ne doivent jamais être persistés ; cache mémoire borné. | 06, 07 |
| C6 | La refonte UI a construit `packages/ui/src/viz` (SVG, tokens, `standard-dataviz.md`). ECharts/uPlot/dockview casseraient ce socle. | Garder `@see/ui/viz`, l'étendre ; panneaux redimensionnables maison, pas de docking. | 01, 08, 09 |
| C7 | Les budgets de la spec sont incohérents entre eux (surface 25×25×300 vs draft 500 runs). Mesure réelle : 100 000 runs ≈ 0,5 s sur poste dev, 5 000 runs × 36 mois ≈ 70 ms. | Recalibrer les budgets en phase 01 sur machine modeste ; surface = action explicite, progressive et annulable. | 01, 11 |
| C8 | La cible « ≥ 50 i/s » n'est tenable que si le `draft` descend sous ~25 ms, ce qui est plausible (mesure de phase 01 ≈ 10 ms pour 500 runs × 36 mois). | Viser 30–60 i/s réels ; **jamais** interpoler des chiffres pour faire croire à du 50 i/s. | 04, 09 |
| C9 | Avec CRN la métrique est déterministe mais reste **en escalier** (probabilités). Nelder-Mead est inadapté. | Recherche par coordonnées + dichotomie sur levier monotone, budget d'évaluations. | 11 |
| C10 | « Aucun nombre absent du payload » est naïf : arrondis, milliers, `%`, unités, fourchettes. | Validateur numérique dédié + repli déterministe. | 12 |
| C11 | Le modèle de versions/branches n'existe pas : `scenarios` est plat, `simulation_runs` ne porte ni qualité ni version. | Migration 0006 + sémantique branche/version explicite. | 07 |
| C12 | `SIMULATION_TIMEOUT` et le verrou Rust rendent l'annulation impossible ; le protocole est en `1.7.0`. | Nouveau protocole `simulation.*`, bump de version, test de contrat. | 06 |

**Conséquence sur le calendrier** : les « 7 semaines » de la spec supposent 3 personnes à plein temps et zéro imprévu. Avec 2 personnes, compter 10–12 semaines ; en solo, 17–21 semaines. Le §8 donne le détail et l'ordre de sacrifice.

---

## 2. Découpage en 16 phases

| # | Phase | Objectif | Dépend de | Livrable clé | Jours | Profil |
|---|---|---|---|---|---|---|
| 01 | [Audit, décisions & banc d'essai](01-audit-et-decisions/README.md) | Figer les contrats, mesurer la baseline, écrire les ADR | — | `audit.md`, ADR 0010–0016, `npm run bench` | 3–4 | Senior + produit |
| 02 | [Métriques cockpit](02-moteur-metriques-v3/README.md) | Point mort, trésorerie, bandes mensuelles, besoin de financement | 01 | Nouveaux agrégats + protocole 1.8.0 | 4–5 | Senior Python |
| 03 | [Tirages communs & préfixe](03-moteur-crn-prefixe/README.md) | CRN, blocs `SeedSequence`, cache de tirages | 02 | Moteur stable au glissement | 5–6 | Senior Python |
| 04 | [Calcul progressif & annulation](04-moteur-progressif-annulation/README.md) | `draft`/`final`, partiels, convergence, annulation < 100 ms | 03 | `simulate()` interactif | 3–4 | Senior Python |
| 05 | [Événements & chocs](05-moteur-evenements/README.md) | Modificateurs temporels, catalogue, probabilité | 03 | Événements moteur testés | 4–5 | Senior Python |
| 06 | [IPC de flux & concurrence](06-ipc-flux-concurrence/README.md) | Protocole streaming, sidecar non bloquant, dispatcher Rust | 04 | `simulation.*` bout en bout | 7–8 | Senior Python + Rust |
| 07 | [Persistance, versions & branches](07-persistance-runs-versions/README.md) | Migration 0006, runs finaux, snapshots, `.simproj` | 02 | Modèle de données V3 | 4–5 | Intermédiaire Python |
| 08 | [Session UI & commandes](08-ui-session-commandes/README.md) | Store, undo/redo, dispositions, recalcul piloté | 06, 07 | Socle d'état réversible | 4–5 | Senior TS |
| 09 | [Cockpit 2D](09-cockpit-2d/README.md) | KPI, éventail, seuil, hypothèses 3 poignées, fantômes | 08 | **Jalon A** | 8–10 | Senior TS + UI |
| 10 | [Temps & événements UI](10-temps-et-evenements-ui/README.md) | Curseur de temps, histogrammes, frise d'événements | 09, 05 | Pilotage temporel | 5–6 | Intermédiaire UI |
| 11 | [Analyse interactive](11-analyse-interactive/README.md) | Surface 2D, heatmap, tornado, recherche d'objectif | 09 | **Jalon B** | 7–8 | Senior Python + TS |
| 12 | [Trajectoires, provenance & explication](12-trajectoires-provenance/README.md) | Accès aux runs, provenance, LLM vérifié | 09, 06 | « D'où vient ce chiffre ? » | 6–7 | Senior Python + UI |
| 13 | [Branches & comparaison](13-branches-comparaison/README.md) | Duplication, diff, côte à côte, versions nommées | 07, 09 | Comparaison de scénarios | 4–5 | Intermédiaire UI |
| 14 | [Vue 3D & repli](14-vue-3d/README.md) | Surface 3D, nuage, fallback WebGL | 11 | **Jalon C** | 5–6 | Senior TS/3D |
| 15 | [Onboarding, exemple & pitch](15-onboarding-exemple-pitch/README.md) | Projet d'exemple sourcé, parcours < 2 min, dossier | 09, 11 | Démo installable | 7–8 | Produit + UI |
| 16 | [Durcissement & lancement](16-durcissement-lancement/README.md) | Signature, MAJ, légal, E2E, machine modeste | toutes | **Jalon D** | 8–10 | Senior infra |

**Total** : 85–105 jours-développeur. À 3 personnes : ~7 semaines calendaires. À 2 : 10–12 semaines. En solo : 17–21 semaines.

---

## 3. Graphe de dépendances et jalons

```
01 ─▶ 02 ─▶ 03 ─▶ 04 ─▶ 06 ─┐
        │      └────▶ 05 ────┼────▶ 10
        └────▶ 07 ───────────┼─▶ 08 ─▶ 09 ─┬─▶ 11 ─▶ 14
                                       │     ├─▶ 12
                                       │     └─▶ 13
                                       └────────▶ 15 ─▶ 16
```

Trois couloirs peuvent avancer en parallèle après la phase 02 :

- **Moteur** : 03 → 04 → 05.
- **Données** : 07 (migration, versions) en parallèle de 03–05.
- **UI** : ne démarre réellement qu'après 06 + 07 (phase 08), puis 09.

**Jalons**

- **Jalon A — cockpit réactif** (fin 09) : on déplace un curseur, la courbe réagit, la graine est visible, le résultat final arrive au relâchement. → **Premier test utilisateurs**.
- **Jalon B — pilotage** (fin 11, avec 12 en cours) : événements, curseur de temps, objectif, heatmap, tornado, provenance.
- **Jalon C — 3D** (fin 14) : la 3D fonctionne ou le repli 2D se déclenche proprement.
- **Jalon D — lancement** (fin 16) : produit signé, installable, utilisable par un inconnu sans aide.

> Les jalons A, B, C sont des points de **décision**, pas seulement des livraisons : les retours utilisateurs peuvent réordonner le §7.

---

## 4. Rôles et répartition senior / intermédiaire

### 4.1 Ce qui exige un senior

- CRN, propriété de préfixe, cache de tirages, inversion de lois sans scipy (phase 03).
- Concurrence sidecar, writer sérialisé, annulation coopérative (phase 06).
- Refonte du dispatcher Rust et gestion des requêtes en attente (phase 06).
- Recherche d'objectif sur métrique non lisse et budgets d'évaluation (phase 11).
- State management, commandes inversibles et invalidation des runs (phase 08).
- Validation numérique des explications LLM (phase 12).

### 4.2 Ce qu'un intermédiaire peut porter seul (avec revue de contrat)

- Migration SQLite, repositories, export/import `.simproj` (phase 07).
- Composants de formulaire, panneau d'hypothèses, frise d'événements (phases 09–10).
- Branches et comparaison côté UI (phase 13).
- Textes, onboarding, projet d'exemple, checklists de release (phases 15–16).
- Tests unitaires, fixtures, golden tests, captures de non-régression.

### 4.3 Règles de collaboration

1. **Contrat avant code** : chaque phase commence par figer ses types (schéma protocole, dataclasses, props) et les valider avec la phase aval.
2. **Un seul propriétaire du protocole** à un instant donné : jamais deux branches qui modifient `messages.schema.json` en parallèle.
3. **Revue senior obligatoire** sur : moteur numérique, concurrence, Rust, commandes/undo, migrations destructives.
4. **Pas de merge sans** `npm run typecheck`, `npm run protocol:check`, `npm run ui:check`, tests Python concernés.
5. **Les chiffres ne se codent pas en dur dans l'UI** : ils viennent du payload, même pour les libellés et les échelles.

---

## 5. Conventions transverses

### 5.1 Contrats et versionnement

- **Protocole** : source unique `packages/protocol/schema/messages.schema.json` ; `npm run protocol:generate` ; `npm run protocol:check` en CI.
- **Version protocole** : `1.7.0` aujourd'hui → `1.8.0` en phase 02 → `1.9.0` en phase 05 → `1.10.0` en phase 06 → `1.11.0` en phase 11 → `1.12.0` en phase 12. Le test Rust `sidecar.rs` qui assert `1.7.0` doit être mis à jour à chaque bump.
- **Scénario** : `schemaVersion` passe de `1.0.0` à `1.1.0` en phase 05 (événements). Le moteur doit accepter `1.0.0` et `1.1.0`.
- **Base** : migration `0006` en phase 07 ; `LATEST_SCHEMA_VERSION` et les archives `.simproj` suivent.
- **Moteur** : bump de version mineure à chaque changement de comportement numérique, avec régénération assumée des golden tests.

### 5.2 Règles de calcul

- Aucun calcul de simulation dans React ; les agrégats affichés viennent du sidecar.
- Toute comparaison (fantômes, branches, versions) utilise **la même graine** et la même structure de tirages.
- Les `n` premiers runs d'un calcul à `N` runs sont identiques à un calcul à `n` runs.
- Un run `draft` n'est jamais persisté ni épinglable ; seul un `final` peut l'être.
- Toute métrique affichée porte sa fourchette (ou sa probabilité) et la graine.

### 5.3 Tests

| Niveau | Outil | Où |
|---|---|---|
| Moteur | pytest + hypothesis + golden | `packages/engine/tests/` |
| Stockage | pytest + fixtures de migration | `packages/storage/tests/` |
| Sidecar | pytest + faux moteur | `apps/desktop/src-tauri/sidecar/tests/` |
| Rust | `cargo test` | `apps/desktop/src-tauri/src/sidecar.rs` |
| UI | Vitest + Testing Library (introduits au durcissement de la phase 03, étendus aux phases 08/09) | `apps/desktop/src/**/*.test.tsx` |
| E2E | Playwright en mode web + shim IPC déterministe | `apps/desktop/e2e/` |
| Contrat | `protocol:check` + tests générés | `packages/protocol/test/` |

> L'infrastructure UI existe depuis le durcissement de la phase 03 (Vitest + Testing Library + jsdom, intégrée à `npm test`) ; Playwright E2E reste créé en phase 16. Ne pas attendre la fin pour tester les composants critiques.

### 5.4 Performance

- `npm run bench` doit exister à la fin de la phase 01 : moteur + sidecar + UI.
- Une régression > 20 % sur un budget bloque le merge.
- Les mesures sont consignées dans `docs/perf/` avec la machine, la date, la version du moteur et le commit.

### 5.5 Sécurité et vie privée

- Aucune clé API dans un message, un log, un export ou un payload de provenance.
- Les explications LLM n'envoient que le payload de provenance, jamais le projet entier.
- Les rapports de crash sont opt-in et sans contenu de projet.
- L'app reste utilisable hors ligne ; sans fournisseur configuré, l'explication LLM est remplacée par un texte déterministe.

---

## 6. Budgets de performance corrigés

Mesures de départ sur le poste de développement, rejouées en phase 01 sur la machine de référence modeste (voir la baseline en fin de section) :

| Mesure | Constat actuel | Cible V3 (machine modeste) | Plafond bloquant |
|---|---|---|---|
| `draft` 500 runs × 36 mois | ≈ 12 ms | ≤ 50 ms | 150 ms |
| `final` 5 000 runs × 36 mois | ≈ 70 ms | ≤ 400 ms | 1,5 s |
| Annulation | non supportée | ≤ 100 ms | 250 ms |
| Surface 15×15 × 200 runs | non supportée | ≤ 8 s | 20 s |
| Mise à jour graphique | — | ≤ 16 ms (canvas/SVG léger) | 33 ms |
| Mémoire sidecar | à mesurer | ≤ 500 Mo | 800 Mo |
| Démarrage app | à mesurer | à consigner | — |

Notes :

- La surface 25×25×300 de la spec représente 187 500 runs : le proxy 15×15×200 mesuré à ≈ 1,70 s suggère ≈ 6–8 s en extrapolation linéaire sur la machine de référence, avant surcoût par point. La V3 utilise par défaut **15×15 × 200 runs**, avec progression et annulation, et non un calcul live.
- Le budget « ≥ 50 i/s » de la spec est remplacé par : **30–60 i/s pendant le glissement**, avec affichage explicite de l'état « calcul en cours ». Aucune interpolation de chiffres.
- Les `partial` sont limités à ~1 message toutes les 50 ms et < 500 Ko par message.

**Baseline mesurée en phase 01** (machine de référence modeste, 2026-11-14, commit `1b09972`) : `draft` 500 × 36 = **9,6 ms**, `final` 5 000 × 36 = **63,3 ms**, proxy de surface 15×15 × 200 = **1,70 s**, mémoire sidecar **87 Mo**. Les budgets ci-dessus sont confirmés. Détail et limites : [`docs/perf/baseline.md`](../perf/baseline.md).

---

## 7. Priorités et ordre de sacrifice (signé le 2026-11-17)

Ordre de coupe figé (D2 de [`decisions-lancement.md`](01-audit-et-decisions/decisions-lancement.md)), du premier au dernier :

1. **Phase 14 entière** (vue 3D + nuage 3D) — première coupe ; le **repli heatmap 2D reste obligatoire** et livré.
2. **Mode pitch** (phase 15, partie D2) — l'onboarding et le projet d'exemple sont conservés.
3. **Phase 11 réduite** à la heatmap 2D + objectif mono-levier.

**Jamais coupés** : phases 02–09 (moteur réactif + cockpit 2D), tests de reproductibilité/CRN/golden, phase 16 (durcissement & lancement).

Règle de dérive : si le jalon A glisse de plus de **5 jours**, cet ordre s'applique sans re-débat. Les phases 10, 12 et 13 restent dans le périmètre tant que les jalons tiennent.

---

## 8. Calendrier réaliste et effectifs

| Effectif | Durée | Remarque |
|---|---|---|
| 3 devs + 0,5 produit | 7–8 semaines | **Engagé** : lancement le **15 janvier 2027** (jalon D). |
| 2 devs | 10–12 semaines | Fallback annoncé si l'effectif baisse : février 2027. |
| 1 dev | 17–21 semaines | Janvier abandonné d'office ; 3D et mode pitch coupés : mars 2027. |

Le calendrier inclut les fêtes : la marge de **20 %** est intégrée dans la date du 15 janvier (démarrage mi-novembre 2026, phases 01–03 déjà réalisées).

- **Jalon A** (cockpit 2D, phase 09) : ≈ 12 décembre 2026.
- **Jalon B** (analyse interactive, phase 11) : ≈ 26 décembre 2026.
- **Jalon D** (lancement, phase 16) : **15 janvier 2027**.

La signature Windows est engagée dès la phase 01 (D4), pas en phase 16.

---

## 9. Validation utilisateurs (transverse)

Aux jalons A, B et D :

- 3 à 4 personnes du public visé (porteur de projet, gérant de commerce), 20 min, sans aide.
- Tâches : décrire son projet, lire le point mort, tester « et si je baisse mon prix ? », ajouter un imprévu.
- Mesurer : temps jusqu'au premier résultat, tâches réussies sans aide, points de confusion, compréhension de l'incertitude.
- Consigner dans `docs/V2/validation-utilisateurs.md` (gabarit fourni) ; les constats peuvent modifier §7.

---

## 10. Risques

| Risque | Impact | Mitigation | Phase |
|---|---|---|---|
| CRN mal implémenté (préfixe faux) | Courbes instables, confiance détruite | Tests de préfixe bloquants, golden, revue senior | 03 |
| Sidecar/Rust mal refondus | Freezes, notifications perdues | Tests de concurrence, faux sidecar, timeout explicite | 06 |
| Métriques mal définies | KPI faux ou incompris | Définitions métier écrites et relues avant code | 02 |
| Surface trop lente | Feature inutilisable | Grille réduite, progression, annulation, budget mesuré | 11 |
| Objectif non atteignable mal géré | Promesse mensongère | Message explicite + meilleur compromis, tests | 11 |
| Explication LLM qui invente un chiffre | Perte de confiance | Validateur numérique + repli déterministe | 12 |
| WebGL absent sur WebKitGTK | 3D cassée | Détection + repli 2D, tests Pop!_OS | 14 |
| Migration `.simproj` destructive | Perte de données | Migration 0006 + tests aller-retour + backup | 07 |
| Signature Windows tardive | Lancement bloqué | Démarrer en phase 01, tester sur VM propre | 01, 16 |

---

## 11. Definition of Done globale

Une phase est terminée lorsque :

- [ ] les livrables de la phase existent et sont versionnés ;
- [ ] les critères d'acceptation de la phase sont cochés ;
- [ ] lint, typecheck, tests unitaires et d'intégration verts ;
- [ ] `protocol:check` et `ui:check` verts si concernés ;
- [ ] les budgets de performance sont mesurés (ou la dérogation est consignée) ;
- [ ] les ADR et la documentation de la phase sont à jour ;
- [ ] aucun secret en clair, journalisé ou commité ;
- [ ] le fonctionnement hors ligne est préservé ;
- [ ] aucune régression sur les phases 01–10 de la v2 (tests existants) ;
- [ ] le code est relu par un senior sur les zones listées en §4.1.

---

## 12. Traçabilité avec la spec V3

| Exigence spec | Phase(s) |
|---|---|
| §3.1 CRN, préfixe | 03 |
| §3.2 progressif, annulation, convergence | 04 |
| §3.3 événements | 05 (+ UI 10) |
| §3.4 recherche d'objectif | 11 |
| §3.5 surface | 11 (+ 14) |
| §3.6 runs, trajectoires, provenance | 02, 06, 12 |
| §4 protocole | 06 |
| §5 état, undo, versions, live | 07, 08 |
| §6 cockpit, panneaux, hypothèses | 09 |
| §7 I1–I13 | 09–13 |
| §8 3D | 14 |
| §9 budgets | 01, 04, 11, 14 |
| §10 A–D | 02–16 |
| §11 règles `CLAUDE.md` | 01 (mise à jour) |
| §13 tests utilisateurs | 09, 11, 15, 16 |
| §15 DoD | §11 ci-dessus |

---

## 13. Index des phases

1. [Phase 01 — Audit, décisions & banc d'essai](01-audit-et-decisions/README.md)
2. [Phase 02 — Métriques cockpit](02-moteur-metriques-v3/README.md)
3. [Phase 03 — Tirages communs & préfixe](03-moteur-crn-prefixe/README.md)
4. [Phase 04 — Calcul progressif & annulation](04-moteur-progressif-annulation/README.md)
5. [Phase 05 — Événements & chocs](05-moteur-evenements/README.md)
6. [Phase 06 — IPC de flux & concurrence](06-ipc-flux-concurrence/README.md)
7. [Phase 07 — Persistance, versions & branches](07-persistance-runs-versions/README.md)
8. [Phase 08 — Session UI & commandes](08-ui-session-commandes/README.md)
9. [Phase 09 — Cockpit 2D](09-cockpit-2d/README.md)
10. [Phase 10 — Temps & événements UI](10-temps-et-evenements-ui/README.md)
11. [Phase 11 — Analyse interactive](11-analyse-interactive/README.md)
12. [Phase 12 — Trajectoires, provenance & explication](12-trajectoires-provenance/README.md)
13. [Phase 13 — Branches & comparaison](13-branches-comparaison/README.md)
14. [Phase 14 — Vue 3D & repli](14-vue-3d/README.md)
15. [Phase 15 — Onboarding, exemple & pitch](15-onboarding-exemple-pitch/README.md)
16. [Phase 16 — Durcissement & lancement](16-durcissement-lancement/README.md)
