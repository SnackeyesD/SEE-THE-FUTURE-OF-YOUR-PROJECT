# Architecture v2 : Application desktop « bring your own AI »

Complément de `ARCHITECTURE.md` (v1, web auto-hébergé). Ici : une **application desktop local-first**, où l'utilisateur branche **n'importe quelle IA avec sa propre clé API** (ou un modèle local), dans l'esprit d'un agent de type Hermes : routage de modèles par rôle, outils, profils, permissions.

---

## 1. Ce qui change par rapport à la v1

| Sujet | v1 (web auto-hébergé) | v2 (desktop robuste) |
|---|---|---|
| Client | Web React | App desktop (Tauri) + même UI React |
| IA | 1 fournisseur choisi par nous | **Tout fournisseur**, clé de l'utilisateur (BYOK) |
| Coût LLM | Porté par nous (quotas) | Porté par l'utilisateur (ou 0 avec modèle local) |
| Données | Postgres serveur | **SQLite local**, projets portables, sync optionnelle |
| Hors ligne | Non | **Oui** (avec modèle local, ex. Ollama) |
| Clés API | Côté serveur | **Trousseau du système**, jamais sur nos serveurs |
| Code généré par l'IA | Phase 2 | Plus critique (s'exécute chez l'utilisateur) : sandbox + validation obligatoires |
| Backend cloud | Indispensable | **Optionnel** (sync, benchmarks, partage, mises à jour) |

**Ce qui ne change pas** : le principe *« le LLM comprend et explique, le moteur calcule »* et le package `engine` (identique, réutilisé tel quel).

## 2. Vue d'ensemble

```
┌───────────────────────────────────────────────────────────────────────┐
│                       Application desktop (Tauri 2)                    │
│                                                                       │
│  ┌──────────────────┐   IPC typé   ┌───────────────────────────────┐  │
│  │ UI React / TS    │◀────────────▶│ Shell Rust                    │  │
│  │ chat + dashboard │              │ trousseau OS, fichiers, MAJ,  │  │
│  └──────────────────┘              │ cycle de vie du sidecar       │  │
│                                    └──────────────┬────────────────┘  │
│                                      JSON-RPC (stdio ou localhost+jeton)│
│                                    ┌──────────────▼────────────────┐  │
│                                    │ Sidecar Python (binaire figé) │  │
│                                    │  ├ agent-core (orchestration) │  │
│                                    │  ├ providers (adaptateurs IA) │  │
│                                    │  ├ engine (simulation)        │  │
│                                    │  └ sandbox (scripts générés)  │  │
│                                    └───────┬───────────────┬───────┘  │
│                        SQLite local ◀──────┘               │          │
└────────────────────────────────────────────────────────────┼──────────┘
                                                              │ HTTPS direct, clé de l'utilisateur
                                   ┌──────────────────────────▼───────────┐
                                   │ Fournisseurs IA : Anthropic, OpenAI,  │
                                   │ Gemini, Mistral, DeepSeek, NVIDIA NIM,│
                                   │ OpenRouter, Ollama/llama.cpp, tout    │
                                   │ endpoint compatible OpenAI            │
                                   └──────────────────────────────────────┘

        (optionnel)  ┌──────────────────────────────────────────────────┐
                     │ Services cloud : sync, packs de benchmarks signés,│
                     │ partage de rapports, serveur de mises à jour      │
                     └──────────────────────────────────────────────────┘
```

## 3. Choix de la coquille desktop

**Recommandation : Tauri 2** (Rust + webview) avec l'UI React existante.
- Installateur léger et faible consommation mémoire : important sur des PC modestes et des connexions limitées.
- Accès natif au trousseau, aux fichiers, au système de mise à jour signé.
- Support natif des *sidecars* (binaires externes) pour embarquer le moteur Python.

**Alternative : Electron** si tu préfères rester 100 % TypeScript côté shell (écosystème plus large, mais installateur et RAM plus lourds).

**Cible prioritaire : Windows** (usage dominant), puis Linux, puis macOS.

## 4. Sidecar Python

Le moteur (numpy) et l'orchestration IA tournent dans un processus Python empaqueté en binaire (PyInstaller ou Nuitka), un par OS/architecture.

- **Communication** : JSON-RPC 2.0 sur stdio (le plus simple et sûr) ou HTTP sur `127.0.0.1` avec port aléatoire et **jeton de session** généré à chaque lancement. Les réponses longues (tokens du LLM, progression d'une simulation) passent par des **événements de flux**.
- **Poids** : éviter `pandas` dans le sidecar si numpy suffit (gain de dizaines de Mo). Garder pandas seulement si indispensable aux scripts utilisateur (voir sandbox).
- **Supervision** : le shell Rust démarre, surveille et redémarre le sidecar ; arrêt propre à la fermeture.

## 5. Couche fournisseurs d'IA (« n'importe quelle IA »)

### 5.1 Interface unique

```python
class ProviderAdapter(Protocol):
    id: str
    def list_models(self) -> list[ModelInfo]: ...
    def chat(self, req: ChatRequest) -> AsyncIterator[ChatEvent]: ...   # streaming normalisé
    def capabilities(self, model: str) -> Capabilities: ...
    def test_connection(self) -> TestResult: ...
```

Adaptateurs :
1. **OpenAI-compatible générique** (`base_url` + clé) : couvre OpenAI, DeepSeek, Mistral, NVIDIA NIM, OpenRouter, Groq, Together, Ollama, LM Studio, vLLM, etc.
2. **Anthropic** (API native).
3. **Google Gemini** (API native).
4. Autres au besoin.

Une bibliothèque tierce de passerelle (type LiteLLM) peut accélérer le démarrage, mais **épingler les versions et vérifier les empreintes** de toute dépendance : le sidecar manipule des clés API. Une fine couche maison reste préférable à long terme.

### 5.2 Matrice de capacités (par modèle)

Pour chaque modèle : fenêtre de contexte, appel d'outils natif, sortie structurée native, mode « raisonnement », vision, prix par million de tokens. Elle pilote le comportement :

- Sortie structurée native disponible → on l'utilise.
- Sinon → mode JSON + **validation pydantic + boucle de réparation** (renvoi de l'erreur au modèle).
- Pas d'outils natifs → protocole d'appel d'outils textuel de secours.

### 5.3 Normalisation (leçons apprises des agents multi-modèles)

- **Retirer/normaliser les champs de raisonnement propres à un fournisseur** (ex. `reasoning_details`) avant de renvoyer l'historique à un autre modèle : mélanger modèles « raisonnement » et « sans raisonnement » dans un même fil provoque des erreurs 422.
- **Erreurs typées** : `AuthError` (401/403, message clair « clé invalide ou sans accès à ce modèle »), `RateLimit` (avec attente et reprise), `ContextOverflow`, `ProviderDown`.
- **Reprise** avec attente exponentielle ; **chaîne de repli** (modèle principal → secondaire).

### 5.4 Routage par rôle (profils)

| Rôle | Mission | Modèle conseillé |
|---|---|---|
| `interviewer` | Dialogue de cadrage, extraction du brief | Bon en français et en suivi d'instructions |
| `modeler` | Brief → hypothèses/paramètres structurés | Fiable en sortie structurée |
| `narrator` | Interprétation des résultats | Bon rédacteur |
| `delegate` | Tâches répétitives bon marché (reformulations, résumés) | Modèle économique ou local |
| `coder` (phase 2) | Scripts personnalisés | Fort en code |

L'utilisateur crée des **profils** (ex. « économique », « qualité », « 100 % local ») qui associent un modèle à chaque rôle. Chaque rôle peut utiliser un fournisseur différent.

### 5.5 Écran « Fournisseurs »

Ajout d'une clé → test de connexion → liste des modèles détectés → choix par rôle. Coût estimé affiché avant les opérations volumineuses ; plafond de dépense par projet.

## 6. Outils de l'agent (style Hermes)

Outils exposés au LLM, tous validés par schéma :

| Outil | Rôle | Permission par défaut |
|---|---|---|
| `update_brief` | Écrire/modifier le brief du projet | Auto |
| `set_hypotheses` | Définir les paramètres (distributions, source, confiance) | Auto |
| `run_simulation` | Lancer le moteur (graine, nb de runs) | Auto |
| `compare_scenarios` | Comparer deux scénarios | Auto |
| `get_benchmark` | Interroger la table de référentiels | Auto |
| `web_search` | Recherche (SearXNG auto-hébergé, repli DuckDuckGo, ou clé de l'utilisateur) | Demander |
| `export_report` | PDF / Markdown | Demander |
| `run_custom_script` | Script généré par l'IA (sandbox) | **Toujours demander** (revue du code) |

- **Modèle de permissions** : *auto / demander / refuser*, réglable par outil, et mémorisable par projet.
- Compatible **MCP** (client) en option, pour brancher d'autres outils plus tard.
- Les résultats de recherche web sont traités comme **données non fiables** (défense contre l'injection de prompt).

## 7. Exécution de scripts générés par l'IA (sandbox)

Sur desktop, un script généré s'exécute sur la machine de l'utilisateur : la barrière doit être solide.

**Approche recommandée : Pyodide (Python/WebAssembly) dans un Worker isolé.**
- Isolation forte et identique sur Windows, Linux et macOS, sans droits système.
- numpy et pandas disponibles, **aucun accès réseau ni fichier** hors des données fournies.
- Limites de temps (timeout dur) et de mémoire.

**Garde-fous supplémentaires :**
1. **Revue humaine obligatoire** : le code est affiché, l'utilisateur valide avant exécution.
2. Analyse statique préalable (liste d'imports autorisés, interdiction de `eval`, accès système, etc.).
3. Résultats renvoyés sous forme de données structurées uniquement (tables, séries), validées avant affichage.
4. Journal de tout code exécuté.

Alternative (moins isolée) : sous-processus Python restreint, mais l'isolation diffère selon l'OS et demande plus de travail.

## 8. Données locales

- **SQLite** (WAL), migrations versionnées ; chiffrement optionnel (SQLCipher).
- **Projet portable** : un fichier `.simproj` (archive : base + résultats + métadonnées) qu'on peut copier, sauvegarder ou envoyer.
- Résultats volumineux : Parquet ou JSON compressé à côté de la base.
- **Aucune clé API dans la base** : uniquement dans le trousseau du système (Windows Credential Manager, Keychain, Secret Service).

Tables : `project`, `message`, `brief`, `scenario`, `simulation_run`, `provider_profile` (sans secrets), `usage_log` (tokens, coût), `tool_permission`, `benchmark_pack`.

## 9. Benchmarks hors ligne

- Les référentiels (marges, paniers moyens, saisonnalité, coûts locaux) sont livrés en **packs versionnés et signés** (JSON), embarqués à l'installation et mis à jour en ligne quand une connexion est disponible.
- Chaque valeur porte : source, date, fiabilité, pays/secteur.
- C'est ton avantage différenciant : un contenu local de qualité que les outils génériques n'ont pas.

## 10. Services cloud optionnels

À construire après le noyau desktop, sans jamais être requis pour faire une simulation :

- **Sync** des projets entre appareils (chiffrée de bout en bout si possible).
- **Distribution** des packs de benchmarks et des mises à jour (canal stable/bêta).
- **Partage** de rapports par lien.
- **Comptes et abonnement** si modèle payant (paiement Mobile Money).

Infra « solide » côté cloud : API Django (réutilisée de la v1), PostgreSQL géré avec sauvegardes, stockage objet (R2/S3), file de tâches, CDN, supervision (Sentry, métriques), déploiements reproductibles (Docker, CI/CD), environnements dev/staging/prod.

## 11. Sécurité (synthèse)

- Clés API : trousseau OS ; envoyées **directement** de la machine au fournisseur ; jamais journalisées ni envoyées à nos serveurs.
- IPC : liste d'autorisations (allowlist) des commandes, CSP stricte dans la webview, jeton de session pour le sidecar.
- **Mises à jour signées** (vérification de signature obligatoire) ; **signature du code** des installateurs (certificat Windows, notarisation macOS : prévoir le coût et les délais).
- Télémétrie et rapports de crash : **opt-in**, sans contenu de projet.
- Vie privée : les idées de business sont sensibles ; transparence sur ce qui est envoyé au fournisseur d'IA choisi.
- Dépendances : épinglées, scannées en CI (SAST, audit de dépendances).

## 12. Qualité et exploitation

- **Tests** : moteur (unitaires, propriétés, golden) ; adaptateurs avec serveurs simulés ; **tests de contrat** par fournisseur ; évaluation de l'agent sur un jeu de briefs (taux de brief complet, chiffres inventés = 0) ; parcours E2E de l'app.
- **Panneau de débogage** : trace des appels LLM (prompt, outils, tokens, coût, latence), exportable.
- **CI/CD** : GitHub Actions en matrice (Windows/Linux/macOS) : lint, tests, build du sidecar par OS, bundles Tauri, publication sur GitHub Releases avec mise à jour automatique.
- **Internationalisation** : français par défaut, FCFA, anglais ensuite.

## 13. Structure du monorepo (v2)

```
/
├── apps/
│   ├── desktop/              # Tauri 2 : src-tauri (Rust) + UI React
│   └── cloud/                # (optionnel) Django : sync, benchmarks, partage
├── packages/
│   ├── engine/               # moteur de simulation (inchangé depuis la v1)
│   ├── agent-core/           # orchestration, rôles, outils, permissions
│   ├── providers/            # adaptateurs IA + matrice de capacités
│   ├── sandbox/              # Pyodide worker + analyse statique
│   ├── ui/                   # composants React partagés (desktop + web)
│   └── protocol/             # schémas IPC (JSON-RPC) générés pour TS et Python
├── data/benchmark-packs/
├── infra/                    # CI, signature, scripts de release
├── CLAUDE.md
├── ARCHITECTURE.md           # v1
└── ARCHITECTURE-DESKTOP.md   # v2
```

## 14. Feuille de route

**Étape 0 : Socle (1 sem.)** : monorepo, Tauri + React, sidecar Python « hello », IPC typé, CI sur Windows.
**Étape 1 : Moteur (2 sem.)** : identique à la v1 (core Monte Carlo, `retail_depot`, tests).
**Étape 2 : Fournisseurs (2 sem.)** : trousseau, adaptateur OpenAI-compatible + Anthropic + Gemini, test de connexion, matrice de capacités, profils par rôle, erreurs typées.
**Étape 3 : Agent MVP (2–3 sem.)** : entretien → brief → hypothèses → simulation → 3 graphiques → narration ; permissions ; suivi des coûts ; benchmarks hors ligne.
**Étape 4 : Distribution (1–2 sem.)** : installateurs Windows signés, mise à jour automatique, `.simproj`, export PDF.
**Étape 5 : Extensions** : sandbox Pyodide + scripts personnalisés, MCP, modèles de simulation supplémentaires, services cloud optionnels.

## 15. Décisions à trancher

1. **Tauri ou Electron** (poids de l'installateur vs. tout-TypeScript).
2. **Taille du sidecar** : numpy seul ou avec pandas.
3. **Signature du code Windows** : obtenir un certificat tôt (sinon avertissements SmartScreen qui freinent l'adoption).
4. **Mode de diffusion** : gratuit, licence, ou abonnement (et comment encaisser localement).
5. **Source et validation des benchmarks locaux.**
6. **Cloud dès le départ ou après la preuve d'usage du desktop.**

---

## Annexe : règles supplémentaires pour `CLAUDE.md` (v2)

```markdown
- Les clés API ne vont que dans le trousseau OS ; jamais en base, en logs, ni en variables versionnées.
- Toute communication avec un fournisseur passe par `packages/providers` (aucun appel direct ailleurs).
- Les champs propres à un fournisseur (ex. raisonnement) sont normalisés avant d'entrer dans l'historique commun.
- Toute sortie LLM structurée est validée par schéma ; en cas d'échec, boucle de réparation limitée à N essais.
- Aucun script généré n'est exécuté sans revue humaine et sans sandbox.
- L'app doit rester utilisable hors ligne (avec modèle local) : ne jamais rendre le cloud obligatoire.
- Les types IPC sont générés depuis `packages/protocol` ; ne pas les écrire à la main des deux côtés.
```
