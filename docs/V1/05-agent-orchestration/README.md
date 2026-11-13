# Phase 05 — Agent-core : orchestration, outils, permissions

> **Objectif** : transformer un dialogue en brief structuré, puis en simulations, via des outils validés et des permissions maîtrisées — sans jamais laisser le LLM inventer un chiffre.

**Références** : `ARCHITECTURE-DESKTOP.md` §5.4, §5.3, §6, §12.

---

## 1. Contexte et dépendances

- **Dépend de** : phase 02 (moteur), phase 03 (stockage), phase 04 (fournisseurs).
- **Débloque** : phases 06, 07, 09.
- **Principe** : le LLM pilote le **dialogue** et **choisit les outils** ; le code valide, calcule et persiste.

## 2. Objectifs

1. Pipeline de rôles : `interviewer` → `modeler` → `narrator` (+ `delegate`, `coder`).
2. Machine à états du parcours : idée → entretien → brief → hypothèses → simulations → résultats → narration.
3. Registre d'outils avec schémas JSON stricts et validation.
4. Moteur de permissions (`auto` / `demander` / `refuser`) par outil et par projet.
5. Validation des sorties structurées + boucle de réparation bornée.
6. Défense contre l'injection de prompt (contenus web = données non fiables).
7. Traçabilité complète : prompts, outils, tokens, coût, latence.
8. Option client MCP pour de futurs outils (différée).

## 3. Périmètre

**Inclus**
- `agent-core` : rôles, boucle d'agent, mémoire de fil, outils, permissions.
- Machine à états du brief et des hypothèses.
- Validation de schéma et réparation.
- Journal de débogage exportable.

**Exclu**
- Exécution de scripts IA (phase 07).
- UI détaillée (phase 06, mais contrats exposés ici).
- Contenu des benchmarks (phase 08).
- Client MCP (optionnel, différé).

## 4. Livrables

- [x] `packages/agent-core/` complet.
- [x] Définitions d'outils + schémas.
- [x] Pipeline de rôles et prompts versionnés.
- [x] Moteur de permissions persistant.
- [x] Machine à états du brief.
- [x] Boucle de réparation des sorties structurées.
- [x] Journal de trace exportable (JSON).
- [x] Tests d'évaluation sur un jeu de briefs.
- [x] ADR orchestration, permissions, anti-injection.

## 5. Tâches détaillées

### Lot A — Modèle de conversation et rôles
- [x] Fil de messages normalisé (rôle, contenu, outils, usage).
- [x] Prompts système par rôle, versionnés et testés.
- [x] Passage de relais entre rôles avec contexte minimal nécessaire.
- [x] `delegate` pour reformulations/résumés économiques.
- [x] Limites de contexte et stratégie de résumé.

### Lot B — Machine à états
- [x] États : `idea`, `interviewing`, `brief_draft`, `brief_validated`, `hypotheses_set`, `simulating`, `results_ready`, `narrating`, `done`.
- [x] Transitions autorisées et garde-fous (pas de simulation sans hypothèses valides).
- [x] Reprise après fermeture de l'app.
- [ ] Événements émis vers l'UI (progression, question, résultat).

### Lot C — Outils
- [x] `update_brief` : écrit/modifie le brief (champs requis).
- [x] `set_hypotheses` : distributions, source, confiance, bornes.
- [x] `run_simulation` : graine, nombre de runs, scénario.
- [x] `compare_scenarios` : comparer deux scénarios.
- [ ] `get_benchmark` : interroger les référentiels (phase 08).
- [ ] `web_search` : SearXNG / repli / clé utilisateur (permission « demander »).
- [ ] `export_report` : PDF/Markdown (phase 09).
- [x] `run_custom_script` : **toujours demander**, passe par la sandbox (phase 07).
- [x] Chaque outil : schéma d'entrée/sortie, description courte, erreurs typées.
- [x] Validation systématique avant exécution ; refus explicite sinon.

### Lot D — Permissions
- [x] Modèle `auto` / `demander` / `refuser` par outil.
- [x] Surcharge par projet, mémorisée.
- [ ] UI de demande de permission (contrat exposé à la phase 06).
- [x] Journal des décisions (qui, quoi, quand).
- [x] Valeurs par défaut sûres : scripts et web = demander.

### Lot E — Sorties structurées et réparation
- [ ] Utiliser la sortie structurée native quand disponible (phase 04).
- [x] Sinon mode JSON + validation Pydantic.
- [x] Boucle de réparation : renvoyer l'erreur au modèle, max **N = 2** essais, puis échec explicite.
- [x] Jamais de « réparation » silencieuse d'un chiffre.
- [x] Tests avec sorties invalides, partielles, hostiles.

### Lot F — Sécurité et robustesse
- [x] Contenus de `web_search` traités comme **données non fiables** : délimités, jamais exécutés comme instructions.
- [x] Détection de tentative d'injection et refus.
- [x] Aucun secret dans les prompts/traces.
- [x] Limites : nombre d'itérations, taille de contexte, budget de tokens.
- [ ] Annulation utilisateur propre.

### Lot G — Observabilité
- [x] Trace par tour : prompt (référence), outils, tokens, coût, latence, erreurs.
- [x] Export JSON de la trace.
- [ ] Niveau de log configurable, sans contenu sensible par défaut.
- [ ] (Option) client MCP derrière un drapeau.

### Lot H — Évaluation
- [x] Jeu de 20 à 50 briefs de test (dont cas ambigus).
- [x] Métriques : brief complet, questions pertinentes, **chiffres inventés = 0**, outils appelés correctement.
- [x] Exécution reproductible en CI avec un fournisseur simulé.

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| Boucle d'agent | maison, simple, traçable ; pas de framework lourd au début |
| Validation | Pydantic côté Python (source unique avec le protocole) |
| Permissions | stockées en base, appliquées côté agent, jamais seulement côté UI |
| Réparation | max 2 essais, échec explicite |
| MCP | optionnel, drapeau désactivé par défaut |

## 7. Arborescence concernée

```
packages/agent-core/
├── agent_core/
│   ├── roles.py
│   ├── state_machine.py
│   ├── loop.py
│   ├── memory.py
│   ├── models.py
│   ├── errors.py
│   ├── permissions.py
│   ├── structured.py
│   ├── guardrails.py
│   ├── trace.py
│   ├── eval.py
│   └── tools/
│       ├── base.py
│       ├── brief.py
│       ├── hypotheses.py
│       ├── simulation.py
│       ├── benchmarks.py
│       ├── web.py
│       ├── export.py
│       └── script.py
└── tests/
    ├── test_state_machine.py
    ├── test_tools.py
    ├── test_permissions.py
    ├── test_repair.py
    ├── test_guardrails.py
    ├── test_trace.py
    ├── test_loop.py
    ├── test_eval.py
    └── eval/
```

## 8. Critères d'acceptation

- [x] À partir d'une idée, l'agent pose des questions et produit un brief complet validé.
- [x] Impossible de lancer une simulation sans hypothèses valides.
- [x] Chaque outil est validé par schéma ; une entrée invalide est refusée avec un message clair.
- [x] Les permissions sont appliquées côté agent, pas seulement dans l'UI.
- [x] Un script généré n'est jamais exécuté sans permission explicite.
- [x] Aucune sortie LLM ne contient un chiffre de simulation : les chiffres viennent du moteur.
- [x] Un contenu web hostile ne modifie pas le comportement de l'agent.
- [x] La trace d'un tour est exportable et ne contient aucun secret.
- [x] L'évaluation sur le jeu de briefs est reproductible.

## 9. Tests et qualité

- Tests de machine à états (transitions interdites).
- Tests d'outils (schémas, erreurs, permissions).
- Tests de réparation (invalide → corrigé → échec après N essais).
- Tests d'injection de prompt.
- Tests d'évaluation agent (fournisseur simulé + vrais modèles en non bloquant).
- Tests de reprise de session.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Agent qui hallucine des chiffres | Moteur seul producteur, schémas, évaluation « chiffres inventés = 0 » |
| Brief incomplet | Machine à états + champs requis + relance ciblée |
| Permissions contournées | Application côté agent, journal, tests |
| Coût des appels | Rôle `delegate` économique, budgets, plafond, trace |
| Prompt injection | Délimitation des données, instructions ignorées, tests |
| Complexité des rôles | Commencer par 3 rôles, ajouter `delegate`/`coder` ensuite |

## 11. Estimation

**3 semaines**.

## 12. Definition of Done

- [x] Parcours brief validé → simulation lancé fonctionne en tests.
- [x] Permissions et anti-injection testés.
- [x] Évaluation reproductible avec zéro chiffre inventé.
- [x] Trace exportable sans secret.
- [x] ADR écrits.

## 13. Reste hors phase 05

- UI de conversation, demandes de permission et événements de progression (phase 06).
- Exécution sandboxée de `run_custom_script`, annulation utilisateur (phase 07).
- Clients réels de recherche web, benchmarks et export PDF/Markdown (phases 08 et 09).
- Niveau de log configurable et client MCP optionnel.
