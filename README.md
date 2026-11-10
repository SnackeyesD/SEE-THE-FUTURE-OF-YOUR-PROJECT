# See The Future — desktop

Application desktop **local-first** « bring your own AI » : l'utilisateur branche le fournisseur IA de son choix (clé API personnelle ou modèle local), et le moteur calcule les simulations.

> État actuel : **phase 07 — sandbox & scripts générés**. Le moteur Monte Carlo, les fournisseurs BYOK, l'agent et la persistance locale sont intégrés ; les scripts générés s'exécutent uniquement dans une sandbox Pyodide après revue humaine et sont audités.

## Prérequis

| Outil | Version |
|---|---|
| Node.js | 22 LTS |
| npm | 11 |
| Python | 3.11+ |
| uv | 0.4+ |
| Rust | stable (toolchain MSVC) |
| Visual Studio Build Tools | C++ + Windows SDK |
| WebView2 | installé (Windows 10/11) |

## Démarrage rapide

```powershell
npm install
npm run sidecar:sync
npm run protocol:generate
npm run sandbox:sync
npm run dev
```

`npm run sandbox:sync` copie Pyodide, `numpy` et `pandas` dans `apps/desktop/public/pyodide/` (assets locaux ignorés par Git).

`npm run dev` lance Tauri (UI + shell Rust + sidecar Python). Pour travailler uniquement sur l'UI dans un navigateur :

```powershell
npm run dev:web
```

Le mode navigateur affiche un avertissement : l'IPC Tauri n'y est pas disponible.

## Scripts utiles

| Commande | Rôle |
|---|---|
| `npm run dev` | App desktop complète (Tauri) |
| `npm run dev:web` | UI seule (Vite) |
| `npm run build` | Build desktop (installateur) |
| `npm run build:web` | Build web (typecheck + Vite) |
| `npm run protocol:generate` | Régénère les types TS et Python |
| `npm run protocol:check` | Vérifie que les types générés sont à jour |
| `npm run sidecar:test` | Tests du sidecar Python |
| `npm run sidecar:lint` | Ruff sur le sidecar |
| `npm run engine:test` | Tests du moteur de simulation |
| `npm run engine:lint` | Ruff sur le moteur |
| `npm run engine:sync` | Installe les dépendances du moteur |
| `npm run storage:test` | Tests de la persistance locale |
| `npm run storage:lint` | Ruff sur le stockage |
| `npm run storage:sync` | Installe les dépendances du stockage |
| `npm run sandbox:sync` | Copie Pyodide et télécharge numpy/pandas localement |
| `npm run sandbox:test` | Tests de l'analyse statique et du contrat |
| `npm run sandbox:lint` | Ruff sur la sandbox |
| `npm run typecheck` | TypeScript strict |
| `npm run icons` | Régénère les icônes Tauri |
| `npm test` | Tests JS/TS des workspaces |

## Structure

```
apps/desktop/                 # Tauri 2 (Rust) + UI React
  src/                        # React
  src-tauri/                  # shell Rust
    sidecar/                  # sidecar Python (JSON-RPC)
packages/protocol/            # source unique : schéma JSON → TS + Python
packages/ui/                  # composants partagés
packages/engine/              # moteur de simulation (phase 02)
packages/storage/             # SQLite, repositories, archives .simproj (phase 03)
packages/agent-core/          # orchestration (phase 05)
packages/providers/           # adaptateurs IA (phase 04)
packages/sandbox/             # scripts isolés (phase 07)
data/benchmark-packs/         # référentiels (phase 08)
infra/                        # scripts build, CI, signature
docs/adr/                     # décisions d'architecture
```

## IPC

Le shell Rust et le sidecar Python échangent du **JSON-RPC 2.0** en **NDJSON** sur stdio (une ligne JSON par message). Les types sont générés depuis `packages/protocol/schema/messages.schema.json`.

Commandes disponibles : `ping`, `health`, `log`, `simulate`, cycle de vie `project.*` (liste, création, ouverture, renommage, duplication, archivage, corbeille, suppression, export/import, taille), `project.data`, `project.brief.save`, `project.scenario.save`, `project.simulate`, les méthodes `agent.*` (état, tour, permissions, trace, outils), `provider.*`, `sandbox.*` (analyse, audit, export), `integrity.check` et `storage.backup`.

Voir [`docs/adr/0002-transport-ipc.md`](docs/adr/0002-transport-ipc.md), [`docs/adr/0004-persistance-locale-simproj.md`](docs/adr/0004-persistance-locale-simproj.md) et [`docs/adr/0008-sandbox-scripts-generes.md`](docs/adr/0008-sandbox-scripts-generes.md).

## Dépannage

- **Le statut sidecar est « arrêté »** : vérifier `npm run sidecar:sync`, puis que `apps/desktop/src-tauri/sidecar/.venv/Scripts/python.exe` existe. Sinon définir `SIDECAR_PYTHON`.
- **Rust ne compile pas** : vérifier l'installation de Visual Studio Build Tools (C++ + Windows SDK).
- **`npm run protocol:check` échoue** : lancer `npm run protocol:generate` et committer les fichiers générés.
