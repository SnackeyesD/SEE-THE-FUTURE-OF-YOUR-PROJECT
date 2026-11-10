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

## 6. Critères de validation (DoD)

- [ ] Chaque écran est migré et vérifié dans ses 4 états (vide/chargement/données/erreur).
- [ ] `npm run dev:web` et `npm run dev` fonctionnent sur tout le parcours complet (créer projet → brief → simulation → résultats).
- [ ] Aucun écran n'importe de style en dehors de `packages/ui` + un fichier local *minimal* si nécessaire (documenté).
- [ ] La comparaison avant/après est visiblement justifiée : plus de bleu générique, ambiance data cohérente.
- [ ] `npm run typecheck` et les tests passent à chaque écran migré (pas de dette en fin de phase).

## 7. Dépendances

- Phases 02–04.

## 8. Durée indicative

**4 à 5 jours** (l'écran Résultats et le panel Sandbox prennent chacun une demi-journée à une journée).
