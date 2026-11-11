# Phase 05 — Écrans & parcours : la refonte appliquée

> Objectif : reconstruire les 7 écrans et les 3 panels avec le système (tokens + primitives + viz). À la fin de cette phase, **l'app entière parle le nouveau langage visuel** et l'ancien CSS n'est plus utilisé que résiduellement.

---

## 1. Objet

Appliquer le système sur la surface réelle. Ordre dicté par le parcours utilisateur (ADR 0007) : *Idée → Brief → Hypothèses → Simulation → Résultats → Narration*, plus les écrans d'infrastructure.

## 2. Ordre de migration

| Ordre | Écran / panel | Ce qui change (attendu, à affiner avec l'audit) |
|---|---|---|
| 1 | `SettingsScreen` + `ProvidersPanel` | Écran de référence déjà migré en phase 03 ; finaliser (profils de rôles, statuts fournisseurs, logs en mono) |
| 2 | `ProjectsScreen` | Liste de projets façon « dataset browser » : rangées tabulaires, sparklines d'activité, badges d'état |
| 3 | `InterviewScreen` | Chat du « interviewer » : bulles nettes, composer centré, suggestions actionnables |
| 4 | `BriefScreen` + `HypothesesScreen` | Formulaires structurés : champ + unité + confiance, table d'hypothèses en `DataGrid`, distributions visualisées en sparkline |
| 5 | `SimulationScreen` | Lancement + progression : barres déterminate avec métriques (graine, runs, temps) en mono |
| 6 | `ResultsScreen` | Le chantier vitrine : charts multi-scénarios (séries stables), P10/P50/P90 en `Measure`, narration en lecture fluide |
| 7 | `SandboxReviewPanel` | Revue de code : éditeur mono avec coloration existante, audits en badges, métriques en `DataGrid` |

## 3. Tâches par écran (méthode commune)

Pour chaque écran :
1. **Recadrer la structure** : layout sur la grille (espacement `--sp-*`), hiérarchie titre / eyebrow / contenu.
2. **Remplacer tout CSS local** par les primitives de `packages/ui` ; les classes restantes de `styles.css` spécifiques à l'écran sont supprimées après migration.
3. **Vérifier les états** : vide, chargement, erreur, données — chaque état utilise `Empty`/`Alert`/`Progress` avec message actionnable.
4. **Appliquer le langage data** : trame de fond discrète, mesures en mono, badges d'unité.
5. **Capturer avant/après** dans `refont/05-ecrans-parcours/captures/`.

## 4. Points de design spécifiques

- **RésultatsScreen (le cœur)** : les 3 charts du MVP (ADR 0007) deviennent la preuve visuelle de l'identité data — c'est l'écran qui doit faire dire « c'est un outil de simulation » au premier regard.
- **ProjectsScreen** : l'ambiance « console de données » doit s'y voir — liste dense, monospace, stats par projet, pas des « cards SaaS » aérées.
- **SandboxReviewPanel** : la revue humaine obligatoire (ADR 0006) doit être visuellement **sérieuse** : cadre distinct, badge « code non exécuté », audits en liste typée.
- **Navigation** : les onglets actifs utilisent `--accent` uniquement (interactif), jamais une couleur de série.

## 5. Livrables

| Livrable | Emplacement |
|---|---|
| 7 écrans + 3 panels migrés | `apps/desktop/src/screens/`, `components/` |
| Captures avant/après | `refont/05-ecrans-parcours/captures/` |
| Liste des styles résiduels (à purger en phase 07) | `refont/05-ecrans-parcours/residus-css.md` |

## 5bis. Journal de réalisation (fait)

> Sans IPC en mode web, seul l'écran d'entrée (Projets) est capturable ; le reste du parcours a été vérifié par revue de code + typecheck (constat P1-00 de la phase 01).

1. **Vague 1 — rétokénisation complète de `styles.css`** (zéro changement JSX) :
   - `:root` legacy réduit à des indirections (`--bg/--surface/--surface-soft` → `--ink-0/1/2`) pour `.sandbox-panel` et amis.
   - `body` : halo encre + trame (identité Ink & Signal), `background-attachment: fixed`, `background-size` à **3 calques** (le `--trame` s'étend en 2 dégradés).
   - 0 hex/rgb écrit à la main : alphas `--accent-a*/--ok-a*/--danger-a*/--warn-a*`, fonds `--bg-surface/--bg-inset/--bg-raised`, code `--code-*`, fonts `--font-data`, focus `--focus`, `--veil-overlay`, `--shadow-*`.
   - `brand__mark` redesign : encre + bordure, accent en couleur de texte (pas de dégradé bleu).
2. **Vague 2 — migration JSX des composants gen-1 → primitives `@see/ui`** :
   - `ProvidersPanel` (le plus gros) : Card/CardHeader, Field/SelectField/TextareaField (+ `ui-field-grid__span`), Button, Badge, InlineAlert (titres obligatoires), Table pour le budget.
   - `SandboxReviewPanel` : `.facts` → Table (limites d'analyse).
   - `ResultsScreen` : table de sensibilité → Table (colonnes mono, règle R4).
   - `BriefScreen` : `.inline-fields` (classe CSS déjà morte) → `ui-field-grid`.
   - Écrans déjà sur primitives : Projects, Interview, Simulation, Brief, Hypothèses, Résultats, Settings + shell App.
3. **Purge du CSS mort** (1135 → ~855 lignes, vérifiée par grep TSX avant chaque coupe) : `.app/.header/.eyebrow/.subtitle/.grid/.badge*/.card + .card h2/.facts/.actions/.button--*/.hint/.error/.tabs/.tab*/label global/.form-*/.budget-row/.field-hint/.muted/.ok/.error-inline/.log*/.providers .card--wide`. Voir `residus-css.md` §4–5.
4. **Bug corrigé au passage** : `.brand span { color: var(--muted) }` (0,1,1) écrasait `.brand__mark` (0,1,0) — la marque repassait en gris ; resserré en `.brand div span`.
5. **Vérifications** : typecheck `@see/desktop` + `@see/ui` OK, tests 3/3, probe accent = `rgb(34 211 238)` sur la marque, fonts Inter/JetBrains Mono, captures `entree-apres.png` + `vitrine-fullpage.png`.

## 6. Critères de validation (DoD)

- [x] Chaque écran migré vers les primitives ; les 4 états passent par `Empty`/`Alert`/`Progress` (vérifié par revue de code — parcours non exécutable sans IPC).
- [ ] `npm run dev:web` et `npm run dev` fonctionnent sur tout le parcours complet (créer projet → brief → simulation → résultats) — *nécessite le sidecar Tauri, reporté*.
- [x] Aucun écran n'importe de style en dehors de `packages/ui` + `styles.css` résiduel documenté (`residus-css.md`).
- [x] La comparaison avant/après est visiblement justifiée : plus de bleu générique, ambiance data cohérente (captures + probe).
- [x] `npm run typecheck` et les tests passent (3/3).

## 7. Dépendances

- Phases 02–04.

## 8. Durée indicative

**4 à 5 jours** (l'écran Résultats et le panel Sandbox prennent chacun une demi-journée à une journée).
