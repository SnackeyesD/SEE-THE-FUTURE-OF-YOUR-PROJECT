# Plan d'implémentation — Application desktop « bring your own AI »

> Document maître. Il découpe le projet décrit dans `ARCHITECTURE-DESKTOP.md` (v2) en **10 phases**, chacune documentée dans son propre dossier.

---

## 0. Objet et périmètre

Ce plan couvre la construction de l'application **desktop local-first** décrite dans `ARCHITECTURE-DESKTOP.md` :

- UI React empaquetée avec **Tauri 2** ;
- **sidecar Python** (orchestration agent + moteur de simulation) ;
- **BYOK** : l'utilisateur branche le fournisseur IA de son choix, clé stockée dans le trousseau OS ;
- **SQLite local**, projets portables `.simproj`, fonctionnement hors ligne avec un modèle local ;
- **sandbox** pour les scripts générés par l'IA ;
- **packs de benchmarks** locaux signés ;
- **services cloud optionnels** (sync, partage, mises à jour, comptes) qui ne doivent jamais être requis pour simuler.

**Hypothèses de travail**

1. Le projet cible prioritairement **Windows**, puis Linux, puis macOS.
2. Le fichier `ARCHITECTURE.md` (v1 web) n'est pas présent dans ce dossier : les phases ci-dessous décrivent la **v2 desktop**. Si la v1 doit être conservée, elle devient un client web secondaire réutilisant `packages/engine` et `packages/ui` (hors périmètre de ce plan).
3. On reste sur le principe fondateur : **le LLM comprend et explique, le moteur calcule**. Aucun chiffre de simulation ne doit être produit par le LLM.
4. Le plan est écrit pour une équipe réduite (1 à 4 personnes). Les durées sont indicatives et supposent un temps plein.

---

## 1. Découpage en 10 phases

| # | Phase | Objectif | Dépend de | Livrable clé |
|---|---|---|---|---|
| 01 | [Socle & monorepo](01-socle-monorepo/README.md) | Monorepo, Tauri + React, sidecar Python « hello », IPC typé, CI | — | App qui démarre et dialogue avec le sidecar |
| 02 | [Moteur de simulation](02-moteur-simulation/README.md) | Package `engine` Monte Carlo déterministe (`retail_depot`) | 01 | Moteur testé, reproductible, rapide |
| 03 | [Persistance locale](03-persistance-locale/README.md) | SQLite, migrations, projets portables `.simproj` | 01, 02 | Projets créés/ouverts/exportés sans perte |
| 04 | [Fournisseurs IA & BYOK](04-fournisseurs-ia/README.md) | Trousseau OS, adaptateurs, matrice de capacités, profils | 01 | Connexion testée à OpenAI-compatible / Anthropic / Gemini / Ollama |
| 05 | [Agent-core](05-agent-orchestration/README.md) | Orchestration, outils, permissions, entretien → brief | 02, 03, 04 | Agent qui produit un brief validé et lance des simulations |
| 06 | [Parcours MVP](06-parcours-mvp/README.md) | Vertical slice de bout en bout + UI | 03, 04, 05 | Idée → brief → simulation → 3 graphiques → narration |
| 07 | [Sandbox & scripts](07-sandbox-scripts/README.md) | Pyodide isolé, analyse statique, revue humaine | 05, 06 | Script IA exécuté sans risque, avec audit |
| 08 | [Benchmarks & références](08-benchmarks-references/README.md) | Packs locaux versionnés, signés, sourcés | 02, 03 | `get_benchmark` fiable et traçable |
| 09 | [Rapports & export](09-rapports-export/README.md) | PDF/Markdown, partage optionnel, `.simproj` | 06, 08 | Rapport exportable sans secret |
| 10 | [Distribution & cloud](10-distribution-cloud/README.md) | Installateurs signés, MAJ, télémétrie opt-in, cloud optionnel | Toutes | Produit installable et maintenable |

---

## 2. Séquencement et jalons

```
Phase 01 ─▶ Phase 02 ─▶ Phase 03 ─┐
                    Phase 04 ─────┼─▶ Phase 05 ─▶ Phase 06 ═══ JALON GO / NO-GO
                                   │                    │
                                   │                    ├─▶ Phase 07
                                   │                    ├─▶ Phase 08
                                   │                    └─▶ Phase 09
                                   └─────────────────────────▶ Phase 10
```

**Jalons**

- **J1 — Socle technique** (fin phase 02) : l'app démarre, le sidecar répond, le moteur produit des résultats reproductibles.
- **J2 — Cœur agent** (fin phase 05) : un brief complet peut être produit et une simulation lancée via outils.
- **J3 — Preuve d'usage (GO / NO-GO)** (fin phase 06) : un utilisateur non technique réalise le parcours complet. **Décision explicite : continuer, pivoter ou arrêter.** Ne pas enchaîner les phases 07–10 sans ce retour.
- **J4 — Confiance & contenu** (fin phase 08) : sandbox solide + benchmarks sourcés.
- **J5 — Produit distribuable** (fin phase 10) : installateur signé, mises à jour, cloud optionnel.

---

## 3. Décisions à prendre avant de coder

| Décision | Recommandation | Justification |
|---|---|---|
| Coquille desktop | **Tauri 2** | Installateur léger, faible RAM, sidecars natifs, trousseau OS. Electron seulement si l'équipe refuse Rust. |
| Transport IPC | **JSON-RPC 2.0 sur stdio** | Plus simple et plus sûr qu'un port local ; pas de port à protéger. HTTP localhost + jeton en repli si besoin de flux complexes. |
| Empaquetage sidecar | **Nuitka** (repli PyInstaller) | Meilleure compatibilité numpy, démarrage correct. Prévoir la signature et les faux positifs antivirus. |
| Dépendances Python | **numpy seul dans le moteur**, pandas autorisé dans la sandbox utilisateur | Gain de plusieurs dizaines de Mo sur l'installateur. |
| Base locale | **SQLite WAL** + migrations versionnées ; SQLCipher optionnel | Simple, portable, testable. |
| Signature Windows | **Obtenir le certificat tôt** (phase 01/10) | Sans signature, SmartScreen freine l'adoption. |
| Benchmarks | **Sourcing et validation dès la phase 02** | C'est le vrai différenciant, et le plus long à produire. |
| Cloud | **Après la preuve d'usage (phase 06)** | Éviter de porter une infra inutile avant validation. |
| Monétisation | À trancher avant la phase 10 | Gratuit, licence, abonnement, Mobile Money. |

Ces décisions sont reprises en détail dans les phases concernées et devront être consignées en ADR (`docs/adr/`).

---

## 4. Conventions transverses

### 4.1 Structure cible du monorepo

```
/
├── apps/
│   ├── desktop/              # Tauri 2 : src-tauri (Rust) + UI React
│   └── cloud/                # (optionnel) API Django
├── packages/
│   ├── engine/               # moteur de simulation Python
│   ├── agent-core/           # orchestration, rôles, outils, permissions
│   ├── providers/            # adaptateurs IA + matrice de capacités
│   ├── sandbox/              # Pyodide worker + analyse statique
│   ├── ui/                   # composants React partagés
│   └── protocol/             # schémas IPC générés pour TS et Python
├── data/benchmark-packs/
├── infra/                    # CI, signature, scripts de release
├── docs/adr/                 # décisions d'architecture
├── ARCHITECTURE-DESKTOP.md
├── PLAN-IMPLEMENTATION.md
└── CLAUDE.md
```

### 4.2 Règles non négociables

- **Secrets** : clés API uniquement dans le trousseau OS. Jamais en base, en logs, en fichier versionné, ni dans un rapport.
- **Providers** : tout appel IA passe par `packages/providers`. Aucun appel direct ailleurs.
- **Normalisation** : les champs propres à un fournisseur (ex. raisonnement) sont retirés/normalisés avant d'entrer dans l'historique commun.
- **Sorties structurées** : validées par schéma ; boucle de réparation limitée à N essais ; échec explicite ensuite.
- **Chiffres** : tout chiffre de simulation provient du moteur, jamais du LLM.
- **Scripts générés** : jamais exécutés sans revue humaine ni sandbox.
- **Hors ligne** : le cloud ne doit jamais être requis pour créer un projet, simuler ou exporter.
- **IPC** : types générés depuis `packages/protocol` ; ne pas les écrire à la main des deux côtés.

### 4.3 Qualité

- Lint + format + typecheck obligatoires en CI (Rust `clippy`, TS `eslint`/`tsc`, Python `ruff`/`mypy`).
- Tests unitaires et de contrat à chaque phase ; tests E2E sur les parcours critiques.
- Versionnement sémantique ; journal de changements ; builds reproductibles.
- Télémétrie et rapports de crash **opt-in**, sans contenu de projet.

---

## 5. Estimation globale

| Profil | Durée indicative |
|---|---|
| 1 développeur à temps plein | 24–32 semaines |
| 2 développeurs | 16–20 semaines |
| Équipe de 3–4 (1 desktop, 1 Python/IA, 1 produit/design, 1 data) | 12–16 semaines |

La phase 06 est le point de contrôle : si la preuve d'usage échoue, les phases 07–10 changent ou s'arrêtent. Ne pas planifier la distribution avant ce jalon.

---

## 6. Risques majeurs

| Risque | Impact | Mitigation |
|---|---|---|
| Sidecar Python lourd / détecté par antivirus | Installation et lancement bloqués | Nuitka, signature de binaire, tests sur VM Windows propre dès la phase 01 |
| Qualité insuffisante des benchmarks | Perte du différenciant | Sourcing tracé, revue, packs signés, affichage de la provenance et de la fraîcheur |
| Complexité multi-fournisseurs | Bugs d'intégration, coûts | Matrice de capacités, tests de contrat, adaptateur OpenAI-compatible en priorité |
| Hallucination de chiffres | Perte de confiance | Moteur seul producteur de chiffres, validation de schéma, tests d'évaluation |
| Script IA malveillant | Compromission machine | Pyodide, revue humaine, analyse statique, limites de temps/mémoire |
| Dérive de périmètre | Retard | Jalon GO/NO-GO en phase 06, phases 07–10 conditionnelles |
| Signature de code coûteuse/longue | Adoption freinée | Lancer la démarche tôt, prévoir budget et délais |

---

## 7. Definition of Done globale

Une phase est terminée lorsque :

- [ ] les livrables listés existent et sont versionnés ;
- [ ] les critères d'acceptation de la phase sont cochés ;
- [ ] lint, typecheck et tests passent en CI ;
- [ ] la documentation de la phase et les ADR associés sont à jour ;
- [ ] aucune régression sur les phases précédentes (tests E2E si applicable) ;
- [ ] les secrets ne sont ni en clair, ni journalisés, ni commités ;
- [ ] le fonctionnement hors ligne est préservé (sauf phase 10 explicitement cloud).

---

## 8. Index des phases

1. [Phase 01 — Socle & monorepo](01-socle-monorepo/README.md)
2. [Phase 02 — Moteur de simulation](02-moteur-simulation/README.md)
3. [Phase 03 — Persistance locale & projets portables](03-persistance-locale/README.md)
4. [Phase 04 — Fournisseurs IA & BYOK](04-fournisseurs-ia/README.md)
5. [Phase 05 — Agent-core : orchestration, outils, permissions](05-agent-orchestration/README.md)
6. [Phase 06 — Parcours produit MVP](06-parcours-mvp/README.md)
7. [Phase 07 — Sandbox & scripts générés](07-sandbox-scripts/README.md)
8. [Phase 08 — Benchmarks & données de référence](08-benchmarks-references/README.md)
9. [Phase 09 — Rapports, export & partage](09-rapports-export/README.md)
10. [Phase 10 — Distribution, mises à jour & cloud optionnel](10-distribution-cloud/README.md)

---

## 9. Réponse à ta question : l'idée est-elle bonne ?

**Oui, l'idée de découper en 10 phases est bonne**, à condition d'ajouter six garde-fous (déjà intégrés ici) :

1. **Un index maître** (ce fichier) : sans lui, 10 dossiers deviennent 10 silos incohérents.
2. **Des critères d'acceptation explicites** par phase : sinon « terminé » est une opinion.
3. **Un vertical slice tôt** (phase 06) : tester l'intérêt réel avant d'investir dans la distribution.
4. **Un ordre de dépendances assumé** : ne pas commencer par le cloud ou la sandbox.
5. **Les benchmarks traités tôt** : c'est le contenu différenciant, pas un détail de fin de projet.
6. **Une décision GO/NO-GO** après la phase 06 : c'est le meilleur investissement du plan.

Le découpage proposé respecte ces principes et suit fidèlement l'architecture v2.
