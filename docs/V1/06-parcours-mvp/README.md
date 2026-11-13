# Phase 06 — Parcours produit MVP

> **Objectif** : livrer le **vertical slice** complet — idée → entretien → brief → hypothèses → simulation → 3 graphiques → narration — et décider GO / NO-GO.

**Références** : `ARCHITECTURE-DESKTOP.md` §5.5, §6, §12, §14 (étape 3).

---

## État d'avancement (2026-11-10)

Le vertical slice technique est implémenté et vérifié automatiquement :

- protocole `1.5.0` avec `project.data`, `project.brief.save`, `project.scenario.save`,
  `project.simulate` et l'événement `simulation:progress` ;
- sidecar : persistance brief / scénario / run et progression de la simulation ;
- shell Rust : commandes `project_*`, timeout simulation de 600 s, relai de progression ;
- UI React : projets, entretien, brief, hypothèses, simulation, résultats, réglages ;
- design system minimal dans `packages/ui` et styles Phase 06 ;
- trois graphiques SVG alimentés uniquement par la sortie du moteur ;
- narration d'agent séparée et vérification locale des nombres cités.

Vérifications passées : `typecheck`, `build:web`, `protocol:check`, `agent:test`,
`agent:lint`, `storage:test`, `storage:lint`, `sidecar:test`, `sidecar:lint`,
`cargo fmt --check`, `cargo clippy -D warnings`, `cargo test` (4 tests).

**Encore hors périmètre ou à valider manuellement** :

- test E2E de l'application Tauri sur Windows et test hors ligne avec Ollama ;
- streaming token par token et annulation utilisateur des opérations longues ;
- traduction EN complète (la langue change les libellés de navigation uniquement) ;
- persistance et export de la narration ;
- estimation de coût avant simulation volumineuse et détection automatique d'Ollama ;
- évaluation utilisateur, rapport et décision GO / NO-GO.

---

## 1. Contexte et dépendances

- **Dépend de** : phases 03, 04, 05.
- **Débloque** : phases 07, 08, 09 (conditionnées par le GO).
- **C'est le jalon le plus important du plan** : il valide l'intérêt réel avant d'investir dans la sandbox et la distribution.

## 2. Objectifs

1. Une UI React complète et cohérente pour le parcours principal.
2. Streaming du dialogue et progression des simulations.
3. Écran de brief éditable et d'hypothèses.
4. Dashboard de résultats avec au moins **3 graphiques**.
5. Narration interprétative séparée des chiffres.
6. Fonctionnement hors ligne avec Ollama.
7. Affichage des coûts et des limites.
8. Français par défaut, FCFA, anglais préparé.
9. Protocole d'évaluation utilisateur GO / NO-GO.

## 3. Périmètre

**Inclus**
- Écrans : accueil/projets, onboarding, chat d'entretien, brief, hypothèses, simulation, résultats, réglages.
- États de chargement, erreurs, vide, hors ligne.
- Graphiques : distribution du profit, sensibilité, comparaison de scénarios (ou courbe de rentabilité).
- Narration et export simple.
- i18n FR, formats FCFA.
- Accessibilité de base.

**Exclu**
- Scripts personnalisés (phase 07).
- Benchmarks avancés (phase 08).
- Rapport PDF complet et partage (phase 09).
- Cloud (phase 10).

## 4. Livrables

- [ ] Parcours E2E fonctionnel sur Windows (implémenté, test manuel Tauri à faire).
- [x] UI React complète (design system minimal dans `packages/ui`).
- [x] Intégration agent/moteur via IPC.
- [x] 3 graphiques documentés.
- [x] Narration validée (aucun chiffre produit par le LLM).
- [ ] Mode hors ligne testé avec Ollama.
- [ ] Script et rapport d'évaluation utilisateur.
- [ ] Décision GO / NO-GO consignée.
- [x] ADR UX et gestion d'état.

## 5. Tâches détaillées

### Lot A — Design et composants
- [x] Définir le design system minimal : couleurs, typographie, espacements, composants de base.
- [x] Composants partagés dans `packages/ui`.
- [x] Navigation et mise en page.
- [x] Accessibilité : contraste, focus, clavier, lecteurs d'écran (base).

### Lot B — Écrans
- [x] Accueil : liste des projets, création, ouverture, récents.
- [x] Onboarding : expliquer le BYOK et le local-first.
- [ ] Chat d'entretien : questions et reprise (streaming token par token différé).
- [x] Brief : édition, champs manquants, validation.
- [x] Hypothèses : valeurs, distributions, sources, confiance.
- [ ] Simulation : paramètres et progression (annulation différée).
- [x] Résultats : cartes, 3 graphiques, tableau de sensibilité.
- [x] Narration : texte séparé, références aux graphiques.
- [x] Réglages : fournisseurs, profil de rôles, coûts, langue.

### Lot C — Intégration
- [x] Connexion IPC typée (aucun type écrit à la main).
- [x] Gestion d'état (serveur + local) et invalidation.
- [ ] Streaming des tokens et des événements de simulation (progression seule).
- [x] Gestion des erreurs typées → messages utilisateur.
- [ ] Annulation propre des opérations longues.

### Lot D — Graphiques
- [x] Distribution du profit (histogramme + P10/P50/P90).
- [x] Analyse de sensibilité (tornado ou équivalent).
- [x] Comparaison de scénarios ou courbe de rentabilité.
- [x] Cohérence stricte avec les sorties du moteur (aucun recalcul côté UI).

### Lot E — Narration
- [x] Rôle `narrator` contraint : reçoit uniquement des résultats structurés.
- [x] Interdiction de produire de nouveaux chiffres.
- [x] Vérification automatique : chaque chiffre du texte existe dans les résultats.
- [x] Ton et niveau de langue adaptés au public.

### Lot F — Offline et coûts
- [ ] Détection d'Ollama et configuration en un clic.
- [x] Indicateur hors ligne.
- [ ] Coût estimé avant simulation volumineuse.
- [x] Plafond de dépense et message de blocage.

### Lot G — i18n et formats
- [ ] FR par défaut, EN prêt (fichiers de traduction ; libellés de navigation seulement).
- [x] FCFA par défaut, formatage local.
- [x] Dates et nombres localisés.

### Lot H — Évaluation GO / NO-GO
- [ ] Recruter 5 à 10 utilisateurs cibles non techniques.
- [ ] Scénario : « partir d'une idée, obtenir une simulation et un rapport ».
- [ ] Mesures : parcours terminé sans aide, temps, compréhension des résultats, confiance, intention d'usage.
- [ ] Critères de GO proposés : ≥ 70 % terminent seuls, ≥ 60 % jugent les résultats utiles, aucun blocage critique.
- [ ] Décision écrite : GO / pivot / arrêt.

## 6. Décisions techniques

| Sujet | Choix retenu |
|---|---|
| Graphiques | SVG maison, zéro dépendance runtime, accessible et alimenté par le moteur |
| État | `useState`/`useCallback` locaux, pas de routeur ni de client de requêtes |
| Streaming | progression de simulation par événement IPC ; tokens LLM différés |
| Narration | séparée des chiffres, vérifiée localement avant affichage |
| Design | design system CSS minimal dans `packages/ui`, sobre et lisible |

Détails et justifications : [`docs/adr/0007-parcours-mvp-ui.md`](../docs/adr/0007-parcours-mvp-ui.md).

## 7. Arborescence concernée

```
apps/desktop/src/
├── App.tsx                 # navigation, état du parcours, orchestration IPC
├── screens/
│   ├── ProjectsScreen.tsx
│   ├── InterviewScreen.tsx
│   ├── BriefScreen.tsx
│   ├── HypothesesScreen.tsx
│   ├── SimulationScreen.tsx
│   ├── ResultsScreen.tsx
│   └── SettingsScreen.tsx
├── components/
│   ├── Charts.tsx
│   └── ProvidersPanel.tsx
├── lib/
│   ├── ipc.ts
│   ├── format.ts
│   ├── narration.ts
│   └── logs.ts
└── styles.css
packages/ui/                # design system minimal
```

## 8. Critères d'acceptation

- [ ] Un utilisateur crée un projet et va jusqu'aux résultats sans aide technique.
- [ ] Le parcours fonctionne hors ligne avec Ollama.
- [x] Les 3 graphiques sont cohérents avec les sorties du moteur.
- [ ] Aucun chiffre de la narration n'est absent des résultats (vérification runtime, test UI à ajouter).
- [x] Les erreurs (clé invalide, quota, contexte) sont compréhensibles et actionnables.
- [ ] L'app reste utilisable sur une machine modeste (temps de réponse, mémoire).
- [x] Le coût est visible et le plafond respecté.
- [ ] L'évaluation utilisateur est réalisée et la décision consignée.

## 9. Tests et qualité

- Tests E2E du parcours complet (fournisseur simulé + Ollama).
- Tests de composants critiques.
- Tests d'accessibilité de base.
- Test de cohérence narration/chiffres.
- Test de reprise après fermeture.
- Test de performance perçue (streaming, progression).

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| UX trop technique | Onboarding, vocabulaire clair, tests utilisateurs |
| Résultats peu compréhensibles | Graphiques + narration pédagogique + intervalles |
| Lenteur sur PC modestes | Streaming, chargement progressif, budget mémoire |
| Dépendance à un modèle | Ollama + fallback + profils |
| Périmètre qui gonfle | Geler le MVP, tout le reste en phase 07+ |

## 11. Estimation

**3 à 4 semaines** (dont 1 semaine d'évaluation et d'itérations).

## 12. Definition of Done

- [ ] Parcours E2E validé par des utilisateurs réels.
- [ ] Décision GO / NO-GO écrite.
- [ ] Aucun chiffre inventé (garde-fous en place, validation utilisateur à faire).
- [ ] Mode hors ligne opérationnel.
- [x] ADR UX et état écrits.
