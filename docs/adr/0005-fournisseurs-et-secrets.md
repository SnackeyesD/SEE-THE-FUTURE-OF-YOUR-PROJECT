# ADR 0005 — Fournisseurs IA, secrets et plafonds

## Statut

Accepté — phase 04.

## Contexte

L'application doit accepter n'importe quel fournisseur IA avec la clé de
l'utilisateur, sans rendre le cloud obligatoire. Les clés ne doivent jamais
être persistées en base, dans un fichier de projet, dans les logs ou dans les
arguments de processus. Les coûts doivent rester sous contrôle par projet.

## Décision

### Secrets

- Les clés vivent uniquement dans le trousseau du système via `keyring`
  (Windows Credential Manager, macOS Keychain, Secret Service).
- La base ne stocke qu'une référence `keychainRef` de la forme
  `seefuture:<uuid>`. La référence n'est pas un secret.
- Le shell Rust lit la clé juste avant un appel fournisseur et l'injecte dans
  la requête JSON-RPC. Le sidecar ne reçoit la clé qu'à l'usage, ne la journalise
  pas et ne la renvoie jamais.
- Supprimer un profil supprime d'abord son entrée de trousseau.
- Les messages d'erreur fournisseur sont filtrés (`sanitize_message`) avant
  d'être exposés.

### Abstraction fournisseur

- Tout appel IA passe par `packages/providers` ; aucun client HTTP fournisseur
  n'est créé ailleurs.
- Une interface unique `ProviderAdapter` expose `list_models`,
  `test_connection`, `capabilities` et `chat` en `AsyncIterator[ChatEvent]`.
- Les adaptateurs disponibles sont OpenAI-compatible (OpenAI, DeepSeek,
  Mistral, OpenRouter, Groq, Together, NVIDIA NIM, LM Studio, vLLM, endpoint
  personnalisé), Anthropic, Gemini et Ollama.
- Les champs propres à un fournisseur sont normalisés avant l'historique commun.
- La matrice de capacités est versionnée (`MATRIX_VERSION`) et fournit contexte,
  outils, sortie structurée, raisonnement, vision et prix.

### Erreurs et repli

- Les erreurs sont typées : `AuthError`, `RateLimit`, `ContextOverflow`,
  `ProviderDown`, `ModelNotFound`, `InvalidRequest`, `BudgetExceeded`.
- Les erreurs réessayables utilisent un backoff exponentiel avec jitter et
  respectent `Retry-After`.
- `FallbackAdapter` expose les bascules via des événements `fallback` visibles
  dans l'UI.

### Coûts et plafonds

- Les prix de la matrice sont en USD par million de tokens. Le coût est stocké
  en micro-USD dans `usage_log`.
- Le plafond du projet est stocké dans `project_budgets.limit_micros`
  (`0` = illimité). Avant un appel, le coût maximal est estimé ; si
  `dépensé + estimé` dépasse le plafond, l'appel est bloqué avec l'erreur
  `BudgetExceeded`. L'UI alerte à partir de 80 %.
- Les profils par rôle (`interviewer`, `modeler`, `narrator`, `delegate`,
  `coder`) associent un profil fournisseur et un modèle dans
  `role_assignments`.

## Conséquences

- Le trousseau est une dépendance de l'application desktop ; sans lui, les
  fournisseurs cloud restent inutilisables mais Ollama/local fonctionne.
- Une clé orpheline est possible si l'utilisateur supprime manuellement le
  profil hors application ; elle reste dans le trousseau du système.
- Les prix doivent être maintenus dans la matrice ; un modèle inconnu est
  marqué comme capacité inconnue et un coût nul est enregistré.
- Le plafond est une protection applicative, pas une garantie de facturation :
  le fournisseur peut facturer un dépassement si l'estimation est trop basse.
