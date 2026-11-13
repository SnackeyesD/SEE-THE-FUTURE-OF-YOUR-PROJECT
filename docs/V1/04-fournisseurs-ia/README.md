# Phase 04 — Fournisseurs IA & BYOK

> **Objectif** : permettre à l'utilisateur de brancher n'importe quelle IA avec sa propre clé, stockée dans le trousseau OS, via une couche d'adaptation unique et normalisée.

**Références** : `ARCHITECTURE-DESKTOP.md` §5, §11.

## Statut d'implémentation

Implémenté et testé :

- `packages/providers` : adaptateurs OpenAI-compatible, Anthropic, Gemini, Ollama,
  registre, matrice de capacités versionnée, erreurs typées, retry, fallback,
  normalisation, coûts.
- Trousseau OS (`keyring`) côté Rust, injection de la clé au sidecar uniquement
  à l'usage, suppression de l'entrée avec le profil.
- Protocole IPC `1.3.0` et méthodes `provider.*`.
- Persistance : profils, rôles (`role_assignments`), plafonds
  (`project_budgets`), `usage_log`, export/import/clonage.
- Écran React « Fournisseurs » : projet, profils, test, modèles, rôles,
  plafond, conversation de test, fallback visible.
- Tests : 17 providers, 19 sidecar (dont un faux serveur OpenAI-compatible et
  le blocage budget), 36 storage, 51 engine, 4 Rust.

Reporté à la phase 05 (agent/orchestration) : boucle de réparation des sorties
structurées, protocole d'outils textuel de secours, presets de profils et
estimation de coût avant opération volumineuse dans l'UI.

---

## 1. Contexte et dépendances

- **Dépend de** : phase 01 (IPC, shell, trousseau côté Rust).
- **Débloque** : phases 05, 06.
- **Contrainte** : tout appel IA passe par `packages/providers` ; aucun appel direct ailleurs.

## 2. Objectifs

1. Stockage et lecture des clés dans le **trousseau du système** (jamais en base/logs).
2. Interface `ProviderAdapter` unique.
3. Adaptateurs : **OpenAI-compatible générique**, **Anthropic**, **Google Gemini**, **Ollama/local**.
4. Streaming normalisé (`ChatEvent`) indépendant du fournisseur.
5. **Matrice de capacités** par modèle (contexte, outils, sortie structurée, raisonnement, vision, prix).
6. Erreurs typées, reprise avec backoff, chaîne de repli.
7. Normalisation de l'historique (retirer les champs propres à un fournisseur).
8. Profils par rôle (interviewer, modeler, narrator, delegate, coder).
9. Écran « Fournisseurs » : ajout de clé, test, liste des modèles, coût estimé, plafond.

## 3. Périmètre

**Inclus**
- Trousseau OS et cycle de vie des clés.
- Adaptateurs et registre de fournisseurs.
- Matrice de capacités et normalisation.
- Erreurs, retries, fallback.
- Profils par rôle et suivi des coûts.
- UI de configuration des fournisseurs.

**Exclu**
- Orchestration de l'agent et outils (phase 05).
- Sandbox (phase 07).
- Sync des profils entre appareils (phase 10).

## 4. Livrables

- [ ] `packages/providers/` avec `ProviderAdapter` et adaptateurs.
- [ ] Intégration trousseau côté Rust exposée au sidecar via IPC sécurisé.
- [ ] Registre + matrice de capacités versionnée.
- [ ] Couche d'erreurs typées et politique de reprise.
- [ ] Gestion des profils par rôle et estimation des coûts.
- [ ] Écran « Fournisseurs » (React).
- [ ] Tests de contrat avec serveurs simulés.
- [ ] ADR sécurité des clés et abstraction fournisseurs.

## 5. Tâches détaillées

### Lot A — Trousseau et secrets
- [ ] Rust : lecture/écriture/suppression via Windows Credential Manager, macOS Keychain, Secret Service.
- [ ] Convention de nommage des entrées (par fournisseur + profil).
- [ ] Transmettre la clé au sidecar **uniquement à l'usage**, via IPC (pas d'argument de ligne de commande, pas d'environnement, pas de log).
- [ ] Effacer la clé de la mémoire dès que possible (best effort).
- [ ] Test : la clé n'apparaît ni en base, ni dans les logs, ni dans les traces.
- [ ] Message d'erreur clair si le trousseau est indisponible.

### Lot B — Interface et registre
- [ ] `ProviderAdapter` : `id`, `list_models`, `chat` (async stream), `capabilities`, `test_connection`.
- [ ] `ChatRequest` / `ChatEvent` normalisés (texte, outil, raisonnement, usage, fin).
- [ ] Registre déclaratif : id, type, `base_url` par défaut, auth, capabilities par défaut.
- [ ] Résolution d'un fournisseur par profil/rôle.

### Lot C — Adaptateurs
- [ ] OpenAI-compatible générique (`base_url` + clé) : OpenAI, DeepSeek, Mistral, NVIDIA NIM, OpenRouter, Groq, Together, LM Studio, vLLM.
- [ ] Anthropic natif.
- [ ] Google Gemini natif.
- [ ] Ollama / llama.cpp (local, sans clé).
- [ ] Détection des modèles disponibles et de leurs capacités quand l'API le permet.
- [ ] Streaming normalisé et annulation propre.

### Lot D — Capacités et robustesse
- [ ] Matrice : contexte, outils natifs, sortie structurée native, raisonnement, vision, prix entrée/sortie.
- [ ] Si sortie structurée native : l'utiliser ; sinon mode JSON + validation (la boucle de réparation appartient à l'agent).
- [ ] Si outils natifs absents : protocole d'appels textuel de secours (défini avec la phase 05).
- [ ] Erreurs : `AuthError`, `RateLimit`, `ContextOverflow`, `ProviderDown`, `ModelNotFound`.
- [ ] Backoff exponentiel + jitter ; respect des en-têtes de limite.
- [ ] Chaîne de repli configurable (principal → secondaire → local).
- [ ] Normalisation : retirer `reasoning_details` et champs propriétaires avant réinjection dans l'historique.
- [ ] Comptage des tokens, coût estimé et réel ; `usage_log`.

### Lot E — Profils et UI
- [ ] Profils : « économique », « qualité », « 100 % local », personnalisés.
- [ ] Association rôle → modèle, par profil.
- [ ] Écran : ajouter une clé → tester → lister les modèles → choisir.
- [ ] Affichage du coût estimé avant une opération volumineuse.
- [ ] Plafond de dépense par projet (alerte et blocage).
- [ ] Mode hors ligne : proposer Ollama si détecté.

### Lot F — Tests
- [ ] Serveurs simulés (mock) pour OpenAI, Anthropic, Gemini, Ollama.
- [ ] Tests de contrat : requêtes/réponses conformes aux API.
- [ ] Tests d'erreurs : 401/403, 429, contexte dépassé, timeout.
- [ ] Tests de streaming et d'annulation.
- [ ] Test de non-fuite de secrets (logs, DB, traces, crash reports).
- [ ] Test de normalisation multi-fournisseurs dans un même fil.

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| Priorité adaptateurs | OpenAI-compatible d'abord (couvre le plus de cas), puis Anthropic, Gemini, Ollama |
| Passerelle tierce (LiteLLM) | Option de démarrage seulement ; versions épinglées, empreintes vérifiées ; couche maison à terme |
| Secrets | trousseau OS uniquement |
| Streaming | `AsyncIterator[ChatEvent]` |
| Coûts | table de prix versionnée + calcul par requête |

## 7. Arborescence concernée

```
packages/providers/
├── providers/
│   ├── base.py             # Protocol + modèles normalisés
│   ├── registry.py
│   ├── openai_compatible.py
│   ├── anthropic.py
│   ├── gemini.py
│   ├── ollama.py
│   ├── capabilities.py     # matrice
│   ├── errors.py
│   ├── retry.py
│   └── costs.py
└── tests/
    ├── mocks/
    ├── test_contract_openai.py
    ├── test_contract_anthropic.py
    ├── test_errors.py
    └── test_secrets.py
```

## 8. Critères d'acceptation

- [ ] Une clé saisie est stockée dans le trousseau et n'apparaît nulle part ailleurs.
- [ ] `test_connection` réussit/échoue avec un message clair pour chaque fournisseur.
- [ ] La liste des modèles est récupérée ou saisie manuellement.
- [ ] Un même fil peut changer de modèle sans erreur 422 ni champ propriétaire résiduel.
- [ ] 401/403, 429 et dépassement de contexte sont gérés distinctement.
- [ ] Le fallback fonctionne et est visible dans l'UI.
- [ ] Les coûts sont journalisés et le plafond bloque l'opération.
- [ ] Ollama fonctionne sans connexion Internet.

## 9. Tests et qualité

- Tests de contrat par fournisseur (fixtures réalistes).
- Tests de sécurité des secrets.
- Tests de reprise et de fallback.
- Tests de cohérence de la matrice de capacités.
- Test E2E : ajout de clé → test → sélection → appel simple.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Multiplication des API | Adaptateur générique + tests de contrat + matrice |
| Fuite de clé | Trousseau, IPC ponctuel, tests anti-fuite, logs filtrés |
| Coûts imprévus | Estimation avant exécution, plafond, fallback économique |
| Modèle qui change/disparaît | Liste dynamique, erreurs typées, profils modifiables |
| Réponses propriétaires incompatibles | Normalisation systématique de l'historique |

## 11. Estimation

**2 à 3 semaines**.

## 12. Definition of Done

- [ ] Au moins 3 fournisseurs opérationnels (OpenAI-compatible, Anthropic, Gemini) + Ollama.
- [ ] Aucun secret hors trousseau (test).
- [ ] Profils par rôle fonctionnels.
- [ ] Erreurs et fallback testés.
- [ ] ADR sécurité et abstraction écrits.
