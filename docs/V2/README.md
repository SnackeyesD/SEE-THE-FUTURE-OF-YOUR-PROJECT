# Documentation V2→V3 — Cockpit de simulation

Ce dossier contient la spécification de la V3 et son découpage d'implémentation.

| Document | Rôle |
|---|---|
| [`V3-COCKPIT.md`](V3-COCKPIT.md) | Spécification produit d'origine (intentions, §0–15). |
| [`PLAN-IMPLEMENTATION-V3.md`](PLAN-IMPLEMENTATION-V3.md) | **Document maître** : corrections issues de l'audit, 16 phases, graphe de dépendances, jalons, budgets, rôles. |
| `01-…` à `16-…` | Une phase = un dossier = un `README.md` exécutable (livrables, lots, contrats, tests, critères d'acceptation). |

## Par où commencer

1. Lire `PLAN-IMPLEMENTATION-V3.md` en entier (30 min).
2. Lire la phase assignée + ses phases amont (les contrats d'entrée sont dans les phases précédentes).
3. Ne jamais modifier `packages/protocol/schema/messages.schema.json` sans passer par la phase 06 et relancer `npm run protocol:generate`.
4. Tout écart au plan se consigne dans un ADR (`docs/adr/`) et, si nécessaire, dans le plan maître.

## État d'avancement

| Phase | Statut | Livrables |
|---|---|---|
| 01 — Audit, décisions & banc d'essai | **terminée** (2026-11-14), décisions externes en attente | [`audit.md`](01-audit-et-decisions/audit.md), ADR 0010–0016, [`docs/perf/baseline.md`](../perf/baseline.md), `npm run bench` |
| 02 — Métriques cockpit | **terminée** (2026-11-14), relecture produit en attente | [`02-moteur-metriques-v3/README.md`](02-moteur-metriques-v3/README.md), protocole `1.8.0`, métriques/bandes/CDF/histogrammes, tests V3 |
| 03 — Tirages communs & préfixe | **terminée** (2026-11-14), revue senior en attente | [`03-moteur-crn-prefixe/README.md`](03-moteur-crn-prefixe/README.md), `DrawBank`, transformations `U`/`Z`, tests de préfixe/invariance, moteur `0.2.0` |
| 04 — Calcul progressif & annulation | **terminée** (2026-11-15) | [`04-moteur-progressif-annulation/README.md`](04-moteur-progressif-annulation/README.md), `quality`, partiels throttlés, `CancelToken`, moteur `0.3.0` |
| 05 — Événements & chocs | **terminée** (2026-11-17) | [`05-moteur-evenements/README.md`](05-moteur-evenements/README.md), protocole `1.9.0`, catalogue `EVENT_CATALOG`, modificateurs par bloc, tests/golden |
| 06 — IPC de flux & concurrence | **terminée** (2026-11-18), revue senior en attente | [`06-ipc-flux-concurrence/README.md`](06-ipc-flux-concurrence/README.md), protocole `1.10.0`, `simulation.start`/`cancel`, writer sérialisé, dispatcher Rust non bloquant, [`docs/perf/ipc.md`](../perf/ipc.md) |
| 07 — Persistance, versions & branches | **terminée** (2026-11-18), revue senior en attente | [`07-persistance-runs-versions/README.md`](07-persistance-runs-versions/README.md), migration `0006`, branches/versions, runs épinglés, purge 200 runs / 15 MiB, `.simproj` v6 + lecture v5 |
| 08 — Session UI & commandes | **terminée** (2026-11-18), revue senior en attente | [`08-ui-session-commandes/README.md`](08-ui-session-commandes/README.md), Zustand 5.1, store/slices, `CommandStack` (undo/redo, coalescence 400 ms), `useLiveSimulation` (draft 50 ms / final 400 ms), `PanelGrid` + presets persistés, 46 tests |
| 09 — Cockpit 2D | **terminée** (2026-11-18), test utilisateur en attente | [`09-cockpit-2d/README.md`](09-cockpit-2d/README.md), route `cockpit`, `FanChart` (P10–P90, seuil CDF, fantômes), `KpiBar`, `TriHandleSlider`, `useLiveSimulation` drafts pendant geste, 44 tests ajoutés (107 desktop) |
| 10 — Temps & événements UI | **terminée** (2026-11-21), revue senior consignée dans [`REVUE-PHASE-10.md`](10-temps-et-evenements-ui/REVUE-PHASE-10.md) | frise, catalogue, éditeur d'événements, palette de commandes, protocole `1.11.0` |
| 11 — Analyse interactive | **terminée** (2026-11-21) | [`11-analyse-interactive/README.md`](11-analyse-interactive/README.md), surface 2D CRN, recherche d'objectif, heatmap/tornado, protocole `1.12.0`, [`docs/perf/surface-goalseek.md`](../perf/surface-goalseek.md) |
| 12 — Trajectoires, provenance & explication | **terminée** (2026-11-23) | [`12-trajectoires-provenance/README.md`](12-trajectoires-provenance/README.md), accès borné aux trajectoires/paramètres, payload de provenance, panneau « D'où vient ce chiffre ? », explication LLM vérifiée + repli déterministe, cache mémoire, protocole `1.13.0` |
| 13 — Branches & comparaison | **terminée** (2026-11-23) | [`13-branches-comparaison/README.md`](13-branches-comparaison/README.md), migration `0007` (`archived_at`), branches (liste plate, duplication, renommage, archivage, limite 20), diff pur hypothèses/événements, comparaison de runs avec avertissement graine/moteur, versions nommées et restauration non destructive, protocole `1.14.0` |
| 14 — Vue 3D & repli | **terminée** (2026-11-23), mesures machine en attente | [`14-vue-3d/README.md`](14-vue-3d/README.md), surface 3D et nuage Monte Carlo (≤ 200 trajectoires), contrôles caméra maison, chunk 3D paresseux à 223 kB gzip, détection WebGL/perte de contexte, repli 2D automatique et expliqué, préférence par projet, tests et `bundle:check` |
| 15 — Onboarding, exemple & pitch | **en cours** (2026-11-23) | [`15-onboarding-exemple-pitch/README.md`](15-onboarding-exemple-pitch/README.md), [`IMPLEMENTATION.md`](15-onboarding-exemple-pitch/IMPLEMENTATION.md), import `template.list`/`project.createFromTemplate`, dossier Markdown `report.build`, parcours guidé, ADR 0018, protocole `1.15.0` ; PDF et test utilisateur en attente |
| 16 — Durcissement & lancement | à démarrer | voir le plan maître |

## Règle d'or

Le plan maître corrige plusieurs points de `V3-COCKPIT.md` après audit du code réel (métriques manquantes, IPC mono-thread, bibliothèques de graphiques, budgets). **En cas de contradiction, le plan maître et les phases priment sur la spec d'origine** ; l'écart est justifié dans la section 1 du plan.
