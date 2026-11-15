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

## Règles V3 — cockpit interactif

- **Un seul producteur de chiffres** : le moteur. Aucun calcul de simulation, d'agrégat, de percentile ou de probabilité dans React, Rust ou le LLM.
- **Reproductibilité d'abord** : mêmes tirages de base pour tous les runs ; les `n` premiers runs d'un calcul à `N` runs sont identiques. Toute modification de l'échantillonnage exige des tests de préfixe (ADR 0010).
- **Un run `draft` n'est jamais persisté** et n'est jamais épinglable. Seul un run `final` peut être enregistré, épinglé ou comparé (ADR 0011, 0014). Un **run final** est un calcul de qualité `final` (5 000 runs par défaut), terminé sans annulation, portant sa graine, sa version de moteur et son `runId`.
- **Une comparaison exige la même graine** et la même version de moteur ; sinon l'UI doit avertir explicitement.
- **Pas d'interpolation de chiffres** pour simuler une fluidité : on peut animer l'apparition d'un résultat, jamais ses valeurs. La cible est 30–60 i/s réels, pas une promesse de 50 i/s.
- **Toujours des fourchettes** : P10/P50/P90 et probabilités viennent du payload ; l'UI affiche « non disponible » ou « non atteint », jamais `0` par défaut.
- **Dataviz** : conserver et étendre `@see/ui/viz` (SVG/canvas, tokens, `ui:check`). ECharts, uPlot et dockview sont refusés sauf preuve mesurée (ADR 0012).
- **3D** : Three.js + `@react-three/fiber`, chargement paresseux, détection WebGL, repli heatmap 2D obligatoire. Aucune information exclusive à la 3D (ADR 0013).
- **État UI** : Zustand + commandes inversibles pour les entrées. Les **résultats ne sont pas annulables** : undo restaure les entrées et invalide le run courant (ADR 0014).
- **Pas de nouvelle dépendance de calcul dans le moteur** : numpy et pydantic uniquement. Les lois sont inversées explicitement, sans scipy.
- **Protocole** : `1.8.0` (métriques), `1.9.0` (événements), `1.10.0` (IPC de flux), `1.11.0` (surface/goal seek), `1.12.0` (provenance). Un seul propriétaire du schéma à la fois ; `protocol:generate` puis `protocol:check` obligatoires. `MethodName` ne contient que les méthodes requêtables ; les notifications serveur (ex. `simulate.progress`) vivent dans `NotificationName`.
- **Persistance** : migration `0006` pour branches/versions/qualité ; toute migration destructive exige un test sur base réelle et une sauvegarde.
- **Explication LLM** : payload de provenance minimal, validateur numérique côté sidecar, réparation limitée, repli déterministe hors ligne. Aucune clé, aucun chemin, aucun projet entier dans le payload, les logs ou le cache (ADR 0016).
- **Performance** : toute régression > 20 % sur un budget de `docs/perf/baseline.md` bloque le merge. Mesurer sur la machine de référence modeste, pas sur un poste de développement rapide.
- **Hors ligne** : l'application reste utilisable sans fournisseur IA ; l'explication est alors déterministe.

## Commandes

```powershell
npm install
npm run sidecar:sync
npm run protocol:generate
npm run dev
npm run dev:web
npm run typecheck
npm run protocol:check
npm test
npm run test -w @see/desktop
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
npm run sandbox:test
npm run sandbox:lint
npm run bench
npm run bench:engine
npm run bench:sidecar
npm run bench:ui
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
- `docs/perf` : machine de référence, baseline et rapports `npm run bench`.
- `scripts/perf` : bancs moteur/sidecar/UI et orchestrateur.
- `docs/V2` : plan d'implémentation V3 et une phase par dossier.

## Conventions

- TypeScript strict ; Python typé ; Rust `clippy` sans avertissement.
- Ne pas ajouter de commentaires évidents. Documenter les décisions en ADR.
- Toute nouvelle commande IPC commence par son schéma dans `packages/protocol`.
- **Fichiers générés** : tout changement de `packages/protocol/schema/messages.schema.json` exige `npm run protocol:generate`, puis le commit des fichiers générés (`packages/protocol/src/generated.ts` et `apps/desktop/src-tauri/sidecar/sidecar/protocol_models.py`). Ne jamais les éditer à la main. La CI exécute `npm run protocol:check` dans les jobs web et Python : un schéma modifié sans régénération bloque le merge.
- **Tests UI** : les parcours critiques (simulation, résultats, ouverture de projet) sont couverts par Vitest + Testing Library + jsdom dans `apps/desktop/src/**/*.test.tsx`. `npm test` exécute ces tests avec les tests du protocole.
- Ne pas committer de secrets, de bases locales, de `.simproj` ni de builds.
