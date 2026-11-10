# Phase 01 — Audit & inventaire du design actuel

> Objectif : dresser un état des lieux complet et factuel avant d'écrire la moindre ligne de design. On ne refond bien que ce qu'on a mesuré.

---

## 1. Objet

Produire le **contrat de référence** de la refonte : une cartographie exhaustive de ce qui existe (écrans, composants, classes CSS, couleurs, typographies, comportements), couplée à un diagnostic des problèmes visuels. Ce document servira de checklist pour toutes les phases suivantes.

## 2. Périmètre à inventorier

| Zone | Fichiers | Ce qu'il faut relever |
|---|---|---|
| Écrans | `apps/desktop/src/screens/` (7 fichiers : Brief, Hypotheses, Interview, Projects, Results, Settings, Simulation) | Structure de chaque écran, composants utilisés, classes CSS, éléments absents |
| Panels | `apps/desktop/src/components/` (Charts, ProvidersPanel, SandboxReviewPanel) | API de chaque composant, props, styles appliqués |
| UI partagée | `packages/ui/src/components.tsx` | Liste des primitives exportées, doublons avec `styles.css` |
| Styles | `apps/desktop/src/styles.css` (1528 lignes) | Toutes les classes groupées par usage, tokens implicites de `:root`, gradients, hard-codes |
| Utilitaires | `apps/desktop/src/lib/` (format, narration, logs) | Ce qui influence l'affichage (formats monétaires, nombres, dates) |
| Prototypes | `06-parcours-mvp/`, `09-rapports-export/` | Maquettes HTML/CSS existantes à ne pas perdre |

## 3. Tâches

### 3.1 Inventaire CSS (quantitatif)
- Extraire de `styles.css` la liste de **toutes les classes** avec un usage trié : tokens / layout / composant / écran-spécifique / dataviz / sandbox.
- Relever chaque **valeur hard-codée** : hex, `rgb()`, tailles px, opacités. Les compter et les catégoriser.
- Identifier les **doublons et quasi-doublons** (`.card` vs `.ui-card`, `.button` vs `.ui-button`, `.badge` vs `.ui-badge`, `.log` vs `.sandbox-code`…).

### 3.2 Captures d'état (qualitatif)
- Lancer `npm run dev:web` et capturer chaque écran dans ses états : vide, chargement, données complètes, erreur.
- Noter pour chaque écran : lisibilité, hiérarchie, densité, cohérence des marges, réaction des graphiques.

### 3.3 Diagnostic des problèmes (le cœur de la phase)
Pour chaque écran, écrire ce qui **ne parle pas « données »** aujourd'hui. Exemples attendus :
- Le bleu d'accent `#4f8cff` sert à la fois d'interactif, de chart et de déco : aucune sémantique.
- Les gradients radiaux en fond (`radial-gradient` bleu) donnent une ambiance « hero SaaS », pas « console de données ».
- Les graphs SVG n'ont qu'une couleur de série ; impossible de comparer 3 scénarios.
- Les nombres ne sont pas tous en `tabular-nums` ; les tableaux de chiffres « tremblent ».
- Pas de trame de grille ni de marqueur de mesure ; rien n'évoque un plan de données.

### 3.4 Audit des pratiques (inspiration Snyk/Supernova appliquée)
- **Actionnabilité** (Snyk) : les erreurs et états vides disent-ils quoi faire ? Noter chaque message non actionnable.
- **Source de vérité** (Supernova) : vérifier qu'aucun style n'est défini en double (side CSS / inline / classes utilitaires).
- **Intégration** : lister les endroits où l'UI force des choix (polices OS, tailles fixes) au lieu d'exposer des tokens.

## 4. Livrables

| Livrable | Emplacement |
|---|---|
| Rapport d'audit | `refont/01-audit-design/audit.md` |
| Inventaire des classes | `refont/01-audit-design/inventaire-css.md` |
| Captures d'écran (états) | `refont/01-audit-design/captures/` |
| Liste des messages non actionnables | `refont/01-audit-design/actionnabilite.md` |

## 5. Critères de validation (DoD)

- [ ] Toutes les classes de `styles.css` sont inventoriées et catégorisées.
- [ ] Chaque écran a au moins 2 captures (vide + données).
- [ ] Les 10 problèmes visuels les plus importants sont listés et priorisés (P1/P2/P3).
- [ ] Le rapport sert de contrat : chaque phase suivante peut y faire référence par ID de problème.
- [ ] L'application est **inchangée** — la phase 01 ne modifie aucun fichier de code.

## 6. Durée indicative

**1 à 2 jours** de travail effectif. Ne pas la dépasser : l'audit nourrit le design, il ne le remplace pas.
