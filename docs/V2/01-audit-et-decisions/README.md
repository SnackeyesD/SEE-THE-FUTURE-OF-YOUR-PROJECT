# Phase 01 — Audit, décisions & banc d'essai

> **Objectif** : figer les contrats de la V3 et les budgets réels avant d'écrire du code de production. Aucun comportement ne change dans cette phase ; on réduit l'incertitude.

**Références** : `docs/V2/V3-COCKPIT.md` §0, §9, §10 (V3-0), §14.
**Dépend de** : rien.
**Débloque** : toutes les phases.
**Profil** : senior (moteur + architecture) avec le produit ; 3–4 jours.

---

## 1. Contexte

La spec V3 a été écrite sans audit du code. Plusieurs affirmations sont fausses ou incomplètes : les métriques cockpit n'existent pas, l'IPC est mono-thread, le transport Rust est bloquant, l'UI a déjà un système de dataviz maison, et les budgets de performance ne sont pas comparables entre eux. Cette phase produit les preuves et les décisions qui rendent les 15 phases suivantes exécutables.

## 2. Périmètre

**Inclus**

- Cartographie du code réel vs spec.
- Mesures de référence reproductibles.
- ADR 0010 à 0016.
- Mise à jour de `CLAUDE.md` (règles V3).
- Figement du périmètre et de l'ordre de sacrifice.
- Démarrage de la démarche de signature Windows.

**Exclu**

- Toute modification de comportement fonctionnel.
- Les prototypes 3D (phase 14) et les maquettes détaillées (phase 09).

## 3. Livrables

- [x] `docs/V2/01-audit-et-decisions/audit.md` : tableau écart spec ↔ code, fichier par fichier.
- [x] ADR `docs/adr/0010-tirages-communs-prefixe.md`.
- [x] ADR `docs/adr/0011-ipc-flux-annulation-concurrence.md`.
- [x] ADR `docs/adr/0012-dataviz-panneaux-cockpit.md`.
- [x] ADR `docs/adr/0013-vue-3d-et-repli.md`.
- [x] ADR `docs/adr/0014-etat-commandes-undo-versions.md`.
- [x] ADR `docs/adr/0015-metriques-et-evenements.md`.
- [x] ADR `docs/adr/0016-explication-llm-provenance.md`.
- [x] `docs/perf/machine-reference.md` + `docs/perf/baseline.md`.
- [x] `npm run bench` opérationnel (script racine + rapport JSON/Markdown).
- [x] `CLAUDE.md` complété par les règles V3 (reprises de la spec §11, corrigées).
- [x] Dossier de signature Windows ouvert (`signature-windows.md`, décision et plan B à finaliser par le produit).

## 4. Tâches détaillées

### Lot A — Audit du code existant

- [x] Moteur : relever les agrégats réellement produits (`Metrics`, `MonthlyAverages`, `BreakEven`, `SensitivityEntry`) et les comparer aux KPI de la spec.
- [x] Moteur : relever le mode d'échantillonnage actuel (`sample_hypothesis` par clé triée, bruit séparé) et ses limites.
- [x] Sidecar : décrire la boucle `RpcServer.serve()`, le `RequestContext`, la persistance de `project_service.simulate()`.
- [x] Rust : décrire `SidecarManager::request_with`, le `Mutex` tenu pendant l'attente, le routage des notifications.
- [x] Stockage : lister les tables et migrations ; vérifier l'absence de versions/branches.
- [x] UI : lister les composants `@see/ui/viz`, les écrans, l'état actuel (pas de store), les conventions CSS/tokens.
- [x] Protocole : version `1.7.0`, méthodes existantes, génération TS/Python.
- [x] Agent : outils `run_simulation` / `compare_scenarios`, permissions, accès aux hypothèses.
- [x] Consigner chaque écart dans `audit.md` avec : constat, preuve (fichier+ligne), impact, phase de correction.

### Lot B — Banc d'essai

- [x] Créer `packages/engine/bench/bench_engine.py` : scénario de référence 36 mois, mesures draft/final/surface simulée, sortie JSON stable.
- [x] Ajouter `engine:bench` au `package.json` racine (via `uv run`).
- [x] Créer `scripts/perf/bench_sidecar.py` : RSS, latence IPC, annulation.
- [x] Créer `scripts/perf/bench_ui.mjs` ou un test navigateur : fps pendant glissement, temps de mise à jour d'un graphique.
- [x] Ajouter `npm run bench` qui exécute les trois et écrit `docs/perf/latest.json` + un résumé Markdown.
- [x] Mesurer la baseline : 500/5 000 runs × 36 mois, surface 15×15×200, démarrage, mémoire.
- [x] Définir la **machine de référence modeste** (CPU 2018–2020, 8 Go, pas de GPU dédié) et documenter ses caractéristiques.

### Lot C — Décisions

- [x] ADR 0010 : CRN, slots de tirages, blocs, préfixe, cache, compatibilité avec l'ADR 0003.
- [x] ADR 0011 : worker sidecar, writer sérialisé, annulation, dispatcher Rust, runId/seq, backpressure.
- [x] ADR 0012 : **garder `@see/ui/viz`** (SVG/canvas maison), panneaux redimensionnables maison, refus d'ECharts/uPlot/dockview sauf preuve contraire. Tracer le budget de bundle.
- [x] ADR 0013 : Three.js + `@react-three/fiber`, chargement paresseux, détection WebGL, repli heatmap.
- [x] ADR 0014 : store Zustand, commandes inversibles, ce qui n'est **pas** annulable (résultats), versions/branches.
- [x] ADR 0015 : définitions métier (point mort, trésorerie négative, besoin de financement), schéma d'événements, compatibilité scénario.
- [x] ADR 0016 : payload de provenance, validateur numérique, repli déterministe, cache et vie privée.

### Lot D — Cadrage produit et lancement

- [ ] Figer la liste des fonctionnalités janvier et l'ordre de sacrifice (reprendre le §7 du plan maître).
- [ ] Valider le secteur du projet d'exemple (phase 15) et lancer le sourcing des benchmarks.
- [x] Ouvrir la démarche de signature Windows (Certificate Authority, EV ou standard, délais).
- [x] Mettre à jour `CLAUDE.md` : règles V3, commandes `npm run bench`, interdiction d'interpolation de chiffres, définition de « run final ».
- [x] Écrire le protocole de test utilisateurs (jalons A/B/D).

## 5. Contrats à figer

### 5.1 Définitions métier (reprises en phase 02)

| Métrique | Définition |
|---|---|
| Point mort (mois) | Premier mois où le **profit net cumulé** ≥ 0 ; `null` si non atteint sur l'horizon. |
| Trésorerie négative | Minimum de la trésorerie mensuelle < 0. |
| Besoin de financement | `max(0, -min(trésorerie mensuelle))`, en P50 et P90. |
| P(point mort ≤ N) | Proportion de runs dont le point mort est ≤ N mois. |
| Fourchette | P10/P50/P90, jamais une valeur seule. |

### 5.2 Budgets (à confirmer par mesure)

- `draft` 500 × 36 : ≤ 50 ms (plafond 150 ms).
- `final` 5 000 × 36 : ≤ 400 ms (plafond 1,5 s).
- Annulation : ≤ 100 ms.
- Surface par défaut 15×15 × 200 : ≤ 8 s (plafond 20 s).
- Message `partial` : ≤ 500 Ko, ≤ 1 toutes les 50 ms.

### 5.3 Versions

- Protocole : `1.8.0` en phase 02, `1.9.0` en phase 05, `1.10.0` en phase 06, `1.11.0` en phase 11, `1.12.0` en phase 12.
- Scénario : `1.0.0` → `1.1.0` en phase 05.
- Base : migration `0006` en phase 07.

## 6. Pièges et décisions

- **Ne pas partir d'ECharts** : le design system fournit déjà lignes, histogrammes, barres divergentes, tokens et règles d'accessibilité. Un changement de librairie exigerait de refaire la refonte.
- **Ne pas « réparer » le Rust en gardant le Mutex** : le live est impossible tant que la commande Tauri bloque sur la réponse.
- **Ne pas promettre 7 semaines en solo** : le plan maître assume 17–21 semaines pour un développeur.
- **Ne pas toucher au protocole** avant l'ADR 0011 et la phase 06 ; sinon les types TS/Python divergent.
- **Le bench doit tourner sur la machine de référence**, pas seulement sur le poste de dev.

## 7. Tests et vérifications

- [x] `npm run bench` produit un JSON reproductible (hors champs de durée variables) et un résumé lisible.
- [x] Les mesures de la machine de référence sont consignées avec date, CPU, RAM, OS.
- [x] Les ADR sont acceptés (statut « accepté ») et référencés dans le plan.
- [x] `audit.md` couvre 100 % des écarts C1–C12 du plan maître.
- [x] `CLAUDE.md` contient les règles V3 et les commandes.

## 8. Critères d'acceptation

- [x] Aucune zone d'ombre sur les métriques : les formules sont écrites et relues.
- [ ] Le propriétaire du protocole est nommé et les bumps sont planifiés.
- [x] La pile de dataviz est tranchée et justifiée par écrit.
- [x] Le budget de la phase 11 est cohérent avec la mesure (pas de 3 s irréaliste).
- [ ] Le calendrier et les effectifs sont validés par l'équipe.
- [x] La signature Windows est lancée ou un plan B est documenté.

## 9. Risques

| Risque | Mitigation |
|---|---|
| Audit trop long, dérive en refonte | Limiter à 4 jours ; tout le reste devient une tâche de phase |
| Mesures non représentatives | Machine de référence dédiée, mesures répétées, médiane |
| Décision dataviz contestée plus tard | ADR avec critères objectifs (bundle, fps, accessibilité) |
| Certificat Windows indisponible | Plan B : signature standard + SmartScreen documenté |

## 10. Definition of Done

- [x] `audit.md`, 7 ADR, baseline perf, `npm run bench` et `CLAUDE.md` à jour.
- [x] Les contrats d'entrée des phases 02 et 06 sont figés.
- [ ] Le périmètre janvier et l'ordre de sacrifice sont signés par le produit.

## 11. Statut d'exécution — 2026-11-14

**Fait**

- Audit complet du code, écarts C1–C12 et écarts secondaires E1–E10 documentés dans [`audit.md`](audit.md).
- ADR 0010–0016 acceptés.
- Baseline mesurée sur la machine de référence modeste et consignée dans [`docs/perf/baseline.md`](../../perf/baseline.md).
- `npm run bench`, `bench:engine`, `bench:sidecar`, `bench:ui` opérationnels.
- `CLAUDE.md` complété par les règles V3.
- Dossier de signature Windows ouvert, plan B documenté.

**Reste à décider (non bloquant pour la phase 02)**

1. **Propriétaire du protocole** : nommer une personne avant la phase 06.
2. **Calendrier et effectifs** : valider le scénario 3 / 2 / 1 personne et la date de janvier.
3. **Périmètre janvier** : signer l'ordre de sacrifice du plan §7 (3D et mode pitch en premier).
4. **Projet d'exemple** : valider le secteur (Bangui ou Brazzaville) et le sourcing des benchmarks avant la phase 15.
5. **Signature Windows** : choisir OV / EV / Azure et lancer la vérification d'identité (phase 01–02), même si la signature est appliquée en phase 16.
6. **Mesure UI** : Vitest + Testing Library ont été outillés au durcissement de la phase 03 ; Playwright reste en phase 16.

Aucune modification de comportement fonctionnel n'a été faite : `engine:test` (52 tests) et `protocol:check` sont verts, le moteur et le protocole sont inchangés.
