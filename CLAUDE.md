# CLAUDE.md — règles du dépôt

## Principes non négociables

- Les clés API ne vont que dans le trousseau OS ; jamais en base, en logs, ni en variables versionnées.
- Toute communication avec un fournisseur IA passe par `packages/providers` (aucun appel direct ailleurs).
- Les champs propres à un fournisseur (ex. raisonnement) sont normalisés avant d'entrer dans l'historique commun.
- Toute sortie LLM structurée est validée par schéma ; en cas d'échec, boucle de réparation limitée à N essais.
- Aucun script généré n'est exécuté sans revue humaine et sans sandbox.
- L'app doit rester utilisable hors ligne (avec modèle local) : ne jamais rendre le cloud obligatoire.
- Les types IPC sont générés depuis `packages/protocol` ; ne pas les écrire à la main des deux côtés.
- Le LLM comprend et explique ; le moteur calcule. Aucun chiffre de simulation ne vient du LLM.

## Commandes

```powershell
npm install
npm run sidecar:sync
npm run protocol:generate
npm run dev
npm run dev:web
npm run typecheck
npm run protocol:check
npm run sidecar:test
npm run sidecar:lint
npm run engine:sync
npm run engine:test
npm run engine:lint
npm run providers:sync
npm run providers:test
npm run providers:lint
npm run storage:sync
npm run storage:test
npm run storage:lint
npm run agent:sync
npm run agent:test
npm run agent:lint
npm run benchmarks:sync
npm run benchmarks:test
npm run benchmarks:lint
```

## Structure

- `apps/desktop/src` : UI React.
- `apps/desktop/src-tauri` : shell Rust, supervision du sidecar.
- `apps/desktop/src-tauri/sidecar` : sidecar Python.
- `packages/protocol` : schéma unique et génération TS/Python.
- `packages/engine` : moteur de simulation (aucune dépendance UI/réseau).
- `packages/storage` : persistance SQLite, repositories et archives `.simproj`.
- `packages/agent-core` : orchestration LLM, outils validés, permissions et traces (aucun accès réseau direct).
- `packages/benchmarks` : chargement, vérification et lookup des référentiels signés.
- `data/benchmark-packs` : packs sourcés, schéma, clés publiques et outils de signature.
- `docs/adr` : décisions d'architecture.

## Conventions

- TypeScript strict ; Python typé ; Rust `clippy` sans avertissement.
- Ne pas ajouter de commentaires évidents. Documenter les décisions en ADR.
- Toute nouvelle commande IPC commence par son schéma dans `packages/protocol`.
- Ne pas committer de secrets, de bases locales, de `.simproj` ni de builds.
