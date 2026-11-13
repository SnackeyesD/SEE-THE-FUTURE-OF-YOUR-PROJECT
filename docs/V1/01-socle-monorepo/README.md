# Phase 01 — Socle & monorepo

> **Objectif** : obtenir un squelette exécutable et testé — Tauri 2 + React + sidecar Python qui se parlent via JSON-RPC typé — avant d'écrire la moindre logique métier.

**Références** : `ARCHITECTURE-DESKTOP.md` §2, §4, §11, §13, §14 (étape 0).

---

## 1. Contexte et dépendances

- **Dépend de** : rien.
- **Débloque** : toutes les autres phases.
- **Décision à figer ici** : Tauri 2 (recommandé) vs Electron. Consigner en ADR.

## 2. Objectifs

1. Monorepo unique, outillé et reproductible.
2. Application desktop minimale qui démarre sur Windows.
3. Sidecar Python empaquetable qui répond à un `ping`.
4. Protocole IPC **généré** pour TypeScript et Python (source unique de vérité).
5. CI qui vérifie lint, types, tests et build sur Windows.
6. Documentation de démarrage (`README`, ADR, `CLAUDE.md`).

## 3. Périmètre

**Inclus**
- Structure du monorepo, gestionnaires de paquets, versions figées.
- Coquille Tauri 2 + webview React/TypeScript.
- Sidecar Python minimal (santé, echo, log).
- Transport JSON-RPC 2.0 sur stdio.
- Cycle de vie du sidecar (démarrage, redémarrage, arrêt propre).
- CI Windows (et squelette Linux/macOS).

**Exclu**
- Moteur de simulation (phase 02).
- Fournisseurs IA (phase 04).
- UI produit (phase 06).

## 4. Livrables

- [ ] `pnpm-workspace.yaml` + `package.json` racine.
- [ ] `apps/desktop/` (React + `src-tauri/`).
- [ ] `packages/protocol/` avec schémas et génération TS/Python.
- [ ] `packages/engine/`, `agent-core/`, `providers/`, `sandbox/`, `ui/` (squelettes vides mais valides).
- [ ] `apps/desktop/sidecar/` (Python) + script de build Nuitka/PyInstaller.
- [ ] `infra/ci.yml` (GitHub Actions) + scripts locaux.
- [ ] `docs/adr/0001-coquille-desktop.md`, `0002-transport-ipc.md`.
- [ ] `README.md` racine (démarrage en < 10 min).
- [ ] `CLAUDE.md` (règles du dépôt).

## 5. Tâches détaillées

### Lot A — Monorepo et outillage
- [ ] Choisir et verrouiller : Node 20 LTS, pnpm, Python 3.11+, `uv` (ou Poetry), Rust stable.
- [ ] Créer les workspaces `apps/*` et `packages/*`.
- [ ] Configurer ESLint + Prettier + `tsc --noEmit`, Ruff + mypy, `rustfmt` + `clippy`.
- [ ] Configurer les versions figées (`.nvmrc`, `.python-version`, `rust-toolchain.toml`, lockfiles).
- [ ] Scripts racine : `dev`, `build`, `test`, `lint`, `typecheck`, `format`.

### Lot B — Protocole IPC
- [ ] Définir les messages de base : `ping`, `health`, `log`, `shutdown`, erreurs JSON-RPC.
- [ ] Définir le framing : JSON par ligne (NDJSON) avec limite de taille par message.
- [ ] Générer les types TS et les modèles Python depuis une source unique (JSON Schema ou Zod → Pydantic).
- [ ] Ajouter un test de non-régression du protocole (hash des schémas générés).

### Lot C — Coquille Tauri
- [ ] Créer l'app Tauri 2 avec front React/Vite.
- [ ] Écran de diagnostic : version, statut sidecar, bouton `ping`, journal.
- [ ] Allowlist stricte des commandes IPC et CSP de la webview.
- [ ] Gérer les chemins de données par OS (dossier applicatif).

### Lot D — Sidecar Python
- [ ] Serveur stdio JSON-RPC 2.0 (lecture/écriture NDJSON, erreurs typées).
- [ ] Gestion `SIGTERM`/fermeture stdin → arrêt propre.
- [ ] Logs structurés vers stderr, **jamais de secret**.
- [ ] Script de build binaire (Nuitka recommandé) par OS/architecture.
- [ ] Supervision côté Rust : démarrage, health-check, backoff de redémarrage, arrêt à la fermeture.

### Lot E — CI/CD
- [ ] GitHub Actions : lint, typecheck, tests, build du sidecar, build Tauri.
- [ ] Matrice Windows (bloquante) + Linux/macOS (non bloquante au début).
- [ ] Artéfacts de build conservés.
- [ ] Vérification qu'aucun fichier de secret n'est commité.

### Lot F — Documentation
- [ ] `README` : prérequis, installation, `pnpm dev`, dépannage.
- [ ] ADR coquille desktop et transport IPC.
- [ ] `CLAUDE.md` : règles de sécurité, structure, commandes.

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| Coquille | Tauri 2 |
| IPC dev | stdio JSON-RPC (NDJSON) |
| IPC prod | même transport ; HTTP localhost + jeton seulement si un besoin de flux l'exige |
| Gestion Python | `uv` |
| Empaquetage sidecar | Nuitka ; PyInstaller en repli |
| Génération de types | une source de schéma → TS + Pydantic |

**Pourquoi stdio** : pas de port ouvert, pas de jeton à gérer, cycle de vie lié au processus parent. Les événements de streaming passent par des notifications JSON-RPC.

## 7. Arborescence concernée

```
/
├── apps/desktop/
│   ├── src/                 # React
│   └── src-tauri/           # Rust
│       └── sidecar/         # Python
├── packages/protocol/
├── packages/engine/         # squelette
├── packages/agent-core/     # squelette
├── packages/providers/      # squelette
├── packages/sandbox/        # squelette
├── packages/ui/             # squelette
├── infra/
├── docs/adr/
├── CLAUDE.md
└── README.md
```

## 8. Critères d'acceptation

- [ ] `pnpm dev` lance l'app sur une machine Windows vierge documentée.
- [ ] L'UI affiche `pong` après un `ping` au sidecar.
- [ ] Tuer le sidecar déclenche un redémarrage automatique et visible.
- [ ] Fermer l'app arrête proprement le sidecar (aucun processus orphelin).
- [ ] Les types IPC sont générés ; les modifier à la main casse la CI.
- [ ] La CI est verte sur Windows (lint, types, tests, build).
- [ ] Aucun secret dans le dépôt (scan automatisé).

## 9. Tests et qualité

- Test unitaire du framing et des erreurs JSON-RPC.
- Test d'intégration : lancement réel du sidecar + `ping` + `shutdown`.
- Test de redémarrage (crash simulé).
- Test de contrat sur les schémas générés.
- Smoke test du build Tauri.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Sidecar non empaquetable | Tester le build binaire dès ce lot, pas à la fin |
| Faux positif antivirus | Signer le binaire tôt, tester sur VM propre |
| Dérive de configuration entre OS | Lockfiles + versions figées + CI matrice |
| Complexité Tauri/Rust | Limiter le Rust au strict nécessaire (fenêtre, sidecar, trousseau, fichiers) |

## 11. Estimation

**1 à 2 semaines** (1 développeur), dont une marge pour l'empaquetage Python et la CI.

## 12. Definition of Done

- [ ] Tous les livrables et critères ci-dessus sont validés.
- [ ] CI verte et reproductible.
- [ ] ADR écrits.
- [ ] `README` permet à un nouvel arrivant de lancer le projet.
- [ ] Aucune régression ultérieure attendue sur le transport IPC.
