# Rapport de test — See The Future (desktop)

> **Note (2026-11-24)** : ce rapport décrit l'état du socle à la fin de la
> phase 07. Le plan V3 a depuis livré les phases 01 à 15, puis la phase 16
> (PDF local, diagnostic nettoyé, journal d'erreurs opt-in, textes légaux
> provisoires). Les chiffres de tests ci-dessous ne sont donc plus à jour :
> la session du 2026-11-24 compte **276 tests UI**, **100 tests sidecar** et
> **17 tests reporting**. Voir [`docs/V2/README.md`](docs/V2/README.md),
> l'[ADR 0018](docs/adr/0018-projet-exemple-dossier-pitch.md),
> l'[ADR 0019](docs/adr/0019-export-pdf-local-et-diagnostic.md) et la
> [note d'implémentation de la phase 16](docs/V2/16-durcissement-lancement/IMPLEMENTATION.md).

**Projet** : `/home/foumou/Documents/projects/SEE-THE-FUTURE-OF-YOUR-PROJECT`
**Remote** : `git@github.com:SnackeyesD/SEE-THE-FUTURE-OF-YOUR-PROJECT.git`
**Branche** : `main` (à jour avec `origin/main`, copie de travail propre)
**Testeur** : `@tester` (profil Hermes)
**Date** : session en cours

---

## 1. Sommaire exécutif

| Suite de tests | Résultat | Détails |
|---|---|---|
| `packages/engine` | ✅ 51/51 | Monte Carlo, distributions, reproductibilité, golden values, CLI |
| `packages/storage` | ✅ 38/38 | SQLite, migrations, projets portables `.simproj`, dépôts, budgets, sandbox audit |
| `packages/sandbox` | ✅ 28/28 | Analyse statique, limites, détection scripts malveillants |
| `packages/providers` | ✅ 17/17 | Adaptateurs OpenAI-compatible/Anthropic/Gemini/Ollama, contrat, retry, fallback, normalisation, erreurs |
| `packages/agent-core` | ✅ 44/44 | Boucle agent, état, permissions, garde-fous, outils, trace, réparation, évaluation |
| `apps/desktop/sidecar` | ✅ 24/24 | RPC JSON-RPC 2.0, santé, ping, simulation, workflow projet, fournisseurs, agent, sandbox |
| **Total** | ✅ **202/202** | **0 échec** |

**TypeScript** (`tsc --noEmit` sur `apps/desktop`) : ✅ compile sans erreur.

**Verdict global** : le socle technique est sain. Tous les tests unitaires, d'intégration et de contrat passent. L'architecture local-first / BYOK / sandbox est cohérente et implémentée.

---

## 2. Détail par package

### 2.1 Moteur de simulation (`packages/engine`)

- **51 tests**, tous verts.
- Couverture : résolution des hypothèses, validation des bornes, valeurs par défaut, distributions (normal, lognormal, triangulaire, uniforme, poisson, empirique), échantillonnage déterministe (PCG64), propriétés de reproductibilité (même graine = mêmes agrégats, graines différentes = résultats différents), histogramme, moyennes mensuelles, sensibilité, point mort, performance (100 000 runs < 2 s), golden values, CLI (`validate` / `run` / `benchmark`).
- **Point fort** : le moteur est le seul producteur de chiffres de simulation (respect de la règle « le LLM comprend et explique, le moteur calcule »). Aucune dépendance UI/réseau.

### 2.2 Persistance locale (`packages/storage`)

- **38 tests**, tous verts.
- Couverture : migrations idempotentes, intégrité SQLite (WAL), backup/rétablissement, base corrompue détectée, écriture concurrente sans corruption, projets portables `.simproj` (export/import avec checksum, rejet travers de chemin, rejet schéma trop récent, rejet fichier manquant/extra), cycle de vie projet (créer/ouvrir/renommer/dupliquer/archiver/corbeille/supprimer), dépôts (briefs, scénarios, runs, permissions, budgets, rôles, usage, traces agent, audits sandbox).
- **Point fort** : aucune colonne de type secret dans le schéma (test `test_schema_contains_no_secret_like_columns` vérifié).

### 2.3 Sandbox (`packages/sandbox`)

- **28 tests**, tous verts.
- Couverture : scripts valides acceptés (numpy/pandas), imports bloqués (`os`, `sys`, `subprocess`, `socket`, `ctypes`, `pyodide`, `js`, etc.), appels bloqués (`eval`, `exec`, `__import__`, `open`, `getattr` sur dunder, etc.), imports relatifs et `*` bloqués, attributs/fonctions/classes dunder bloqués, littéraux trop longs rejetés, syntaxe invalide signalée avec ligne/colonne, fonction `main(data)` requise, limites de taille de code et de sortie.
- **Point fort** : politique statique solide, conforme à l'exigence « aucun script généré n'est exécuté sans revue humaine ni sandbox ».

### 2.4 Fournisseurs IA (`packages/providers`)

- **17 tests**, tous verts (nécessite `pytest-asyncio` et `httpx`).
- Couverture : catalogue de modèles et prix, préfixe de fournisseur, estimation de tokens, contrats de streaming (Anthropic, Gemini, Ollama, OpenAI-compatible), erreurs d'authentification nettoyées, cartographie des erreurs HTTP (401→AuthError, 429→RateLimit, 404 model→ModelNotFound, 5xx→ProviderDown), sanitisation des secrets dans les messages et les payloads d'erreur, fallback avant premier token, retry avec attente exponentielle sur rate-limit, pas de retry sur auth error, abandon après N tentatives.
- **Point fort** : sanitisation systématique des clés API dans les logs et les erreurs (conforme à la règle « jamais en clair, jamais journalisé »).

### 2.5 Agent-core (`packages/agent-core`)

- **44 tests**, tous verts (nécessite `engine`, `providers`, `sandbox` sur le `PYTHONPATH`).
- Couverture : machine à états (transitions autorisées/interdites, pas de simulation sans hypothèses, routage par rôle), boucle agent (exécution outil puis texte, arguments invalides renvoyés au modèle, permission ask puis résume, refus d'outil, limite d'itérations), permissions (défauts sûrs, surcharge par projet, scripts toujours `ask`), outils (brief, hypothèses, simulation, comparaison, web search avec blocage d'injection, export, script custom jamais exécuté sans revue), réparation JSON (fenced, entouré de texte, échec après N tentatives), détection d'injection (DAN, « ignore previous instructions », révélation de clé API), traçage avec redaction des secrets, export de trace en JSON.
- **Point fort** : modèle de permissions `allow/ask/deny` bien implémenté, garde-fous contre l'injection de prompt sur les données web non fiables.

### 2.6 Sidecar (`apps/desktop/src-tauri/sidecar`)

- **24 tests**, tous verts (4 modèle protocole + 20 RPC).
- Couverture : version du protocole correspond au schéma, requêtes JSON-RPC 2.0 valides/invalides, erreur de parse (-32700), requête invalide (-32600), méthode inconnue (-32601), notification sans réponse, ping/health, arrêt propre, simulation déterministe avec notifications de progression, rejet scénario invalide, workflow projet complet (créer → brief → scénario → simuler → données → état agent), cycle de vie projet, export/import `.simproj` avec checksum, intégrité, backup, profils fournisseurs, rôles, budget, chat factice (streaming + blocage budgétaire), état/permissions/outils agent, turn agent avec trace, analyse/audit/export sandbox.
- **Point fort** : l'ensemble des commandes JSON-RPC documentées dans le schéma sont implémentées et testées de bout en bout via un véritable sous-processus sidecar.

---

## 3. Observations qualité du code

### Points forts

1. **Séparation des responsabilités respectée** : le moteur ne dépend ni de l'UI ni du réseau ; les appels IA passent exclusivement par `packages/providers` ; les clés API ne sont jamais en base ni en logs.
2. **Typage strict** : Pydantic v2 avec `extra="forbid"` des deux côtés (TS et Python), schémas JSON-RPC générés depuis une source unique (`packages/protocol/schema/messages.schema.json`).
3. **Sécurité sandbox** : analyse statique AST complète (interdiction d'imports système, d'appels dangereux, d'accès dunder, de littéraux trop longs), fonction `main(data)` obligatoire.
4. **Réproducibilité** : générateurs PCG64 indépendants de l'état global de numpy, même graine = mêmes agrégats bit à bit.
5. **Gestion d'erreurs typée** : `AuthError`, `RateLimit`, `ContextOverflow`, `ProviderDown`, `ModelNotFound`, `BudgetExceeded` avec sanitisation des secrets.
6. **Internationalisation prête** : UI en français par défaut, FCFA, bascule thème clair/sombre, locale `fr`/`en`.

---

## 4. Écarts et recommandations (candidats issues)

Les éléments ci-dessous ne bloquent pas le fonctionnement actuel, mais méritent d'être suivis. Ils peuvent faire l'objet d'issues sur le dépôt GitHub.

### 4.1 Couverture CI (gap)

**` .github/workflows/ci.yml`** ne couvre que :
- **Web (Windows)** : `protocol:check`, `typecheck`, `ui:check`, `npm test`, `build:web`
- **Python (Windows)** : `ruff check` + `pytest` uniquement pour `engine`, `storage`, `sidecar`
- **Rust (Windows)** : `cargo test`

**Manquants** :
- Aucun job Linux / macOS (l'architecture cible Windows d'abord, puis Linux, puis macOS)
- Aucun test `pytest` ni `ruff check` pour `packages/providers`, `packages/agent-core`, `packages/sandbox`
- Aucun test E2E / UI pour le frontend React (aucune suite de tests JS/TS trouvée dans `apps/desktop/src`)

**Recommandation** : ajouter des jobs Linux/macOS, étendre les tests Python aux trois packages manquants, et ajouter une suite de tests UI (Vitest/Playwright) sur les parcours critiques.

### 4.2 Fichiers générés du protocole

`packages/protocol/src/generated.ts` et `apps/desktop/src-tauri/sidecar/sidecar/protocol_models.py` sont auto-générés depuis `messages.schema.json` via `npm run protocol:generate`. Ils sont présents et commits, mais rien n'empêche qu'un contributeur modifie le schéma sans régénérer. Le `protocol:check` dans CI le détecte, mais seulement sur le job web.

**Recommandation** : ajouter `protocol:check` au job Python du CI également, et rappeler dans `CLAUDE.md` que tout changement de schéma doit s'accompagner de la régénération et du commit des fichiers générés.

### 4.3 Gestion d'erreurs dans `sidecar/rpc.py`

La fonction `simulate()` (ligne 89-114) ne capture que `EngineError` et `ValidationError`. Une exception inattendue côté numpy (ex. overflow, memory) remonte comme `INTERNAL_ERROR` générique via le `except Exception` de `RpcServer._handle_line`. Ce n'est pas un bug bloquant, mais le message d'erreur retourné au client est peu diagnostique.

**Recommandation** : ajouter un `except Exception` ciblé dans `simulate()` retournant une erreur plus descriptive (ou au moins logger le traceback complet avant de convertir en `INTERNAL_ERROR`).

### 4.4 Méthode `simulate.progress` dans l'enum `MethodName`

Le schéma JSON-RPC liste `simulate.progress` dans `MethodName` (« Méthodes exposées par le sidecar »), mais il s'agit en réalité d'une **notification** serveur→client (émise via `context.notify()`), pas d'une méthode appelable par le client. Cela est documenté dans la définition `SimulateProgressParams`, mais l'inclusion dans l'enum `MethodName` peut prêter à confusion.

**Recommandation** : retirer `simulate.progress` de l'enum `MethodName` ou ajouter un commentaire clarifiant qu'il s'agit d'une notification uniquement.

### 4.5 Aucun test Rust visible pour la coquille Tauri

Le job Rust du CI lance `cargo test`, mais les fichiers sources Rust (`main.rs`, `lib.rs`, `sidecar.rs`, `keychain.rs`) contiennent des tests (`#[test]` trouvé dans `keychain.rs` et `sidecar.rs`). Il faudrait vérifier que `cargo test` passe effectivement sur la chaîne de toolchain stable (nécessite Visual Studio Build Tools sur Windows, non testable ici sur Linux).

---

## 5. Preuves d'exécution

Toutes les suites de tests ont été exécutées localement avec l'interpréteur Python du projet (3.14.9) et les dépendances installées (`numpy`, `pytest`, `hypothesis`, `pydantic`, `httpx`, `pytest-asyncio`). Aucun test n'a été simulé — tous les résultats proviennent d'une exécution réelle.

Résultat agrégé : **202 tests passés, 0 échec, 0 ignoré**.

---

## 6. Conclusion

La solution est **fonctionnelle et cohérente** à ce stade du projet (fin de la phase 07 — sandbox & scripts générés). Le noyau desktop (moteur, stockage, fournisseurs, agent, sidecar, IPC) est couvert par une suite de tests complète et verte. L'architecture respecte les règles non négociables énoncées dans `CLAUDE.md` et `ARCHITECTURE-DESKTOP.md`.

Les prochaines étapes prioritaires, si l'équipe poursuit au-delà du jalon GO/NO-GO de la phase 06, seraient : élargir la CI (Linux/macOS, packages providers/agent-core/sandbox), ajouter des tests UI, et préparer la signature des installateurs Windows (SmartScreen).

---

*Rapport généré par l'agent `@tester` — aucune modification n'a été apportée au code source lors de cette session.*