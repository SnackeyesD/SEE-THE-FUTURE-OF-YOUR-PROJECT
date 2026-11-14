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
| 04 à 16 | à démarrer | voir le plan maître |

## Règle d'or

Le plan maître corrige plusieurs points de `V3-COCKPIT.md` après audit du code réel (métriques manquantes, IPC mono-thread, bibliothèques de graphiques, budgets). **En cas de contradiction, le plan maître et les phases priment sur la spec d'origine** ; l'écart est justifié dans la section 1 du plan.
