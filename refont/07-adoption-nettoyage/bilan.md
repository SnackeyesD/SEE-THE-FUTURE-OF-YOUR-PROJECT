# Bilan de la refonte « Ink & Signal »

> Phase 07 — bilan honnête : ce qui est livré, ce qui s'est écarté du plan et pourquoi, ce qui reste délibérément hors périmètre.

---

## 1. Livré vs plan

| Phase | Plan | Livré | Écart |
|---|---|---|---|
| 01 Audit | État des lieux + captures | ✅ Audit des 7 écrans, constat **P1-00** (mode web sans IPC : parcours verrouillé sur Projets) | — |
| 02 Tokens | Source de vérité + palette dataviz | ✅ `tokens.css` (10 couches), palette 10 séries validée Viénot (ΔE 13.6 ≥ 12), charte-couleurs.md | — |
| 03 Primitives | 11 composants + vitrine | ✅ Card, Button, Badge, Field/Select/Textarea, InlineAlert, Table, Tabs, Stat, EmptyState, Progress + vitrine `?showcase` | `Stat.unit` ajouté (phase 04) ; leçon cascade documentée (séquence `*/` dans tokens.css) |
| 04 Dataviz | Librairie viz | ✅ LineChart/Histogram/DivergingBars/BarChart/Sparkline/Legend, standard-dataviz.md, Charts.tsx réécrit | + `Stat.unit`, bug signe histogramme + collision tornade corrigés |
| 05 Écrans | 7 écrans + 3 panels migrés | ✅ Tous sur primitives ; rétokénisation complète de styles.css (2 vagues) ; purge des morts | Migration JSX des écrans en réalité **déjà faite en phase 03** pour 5 d'entre eux — la phase 05 a porté sur ProvidersPanel (gros morceau), Sandbox, tables de Résultats, Brief, et la purge |
| 06 Qualité | Contraste AA + light + a11y | ✅ 2 tokens corrigés, thème light complet, `prefers-reduced-motion`, captures dark/light | — |
| 07 Adoption | Purge, doc, garde-fous, bilan | ✅ `:root` gen-1 supprimé, DESIGN.md + README @see/ui, `ui:check` (CI), bilan | — |

## 2. Mesures avant / après

| Mesure | Avant (c02bb8f) | Après (phase 07) |
|---|---|---|
| `styles.css` | 1528 lignes | **856** (−44 %) |
| hex/`rgb()` dans styles.css | 82 | **0** |
| hex dans le TSX | 3 (Charts.tsx) | **0** |
| Sources de styles dans l'app | 1 fichier monolithique | tokens.css + light.css + primitives.css + chart.css + styles.css résiduel (documenté) |
| Composants réutilisables | 0 (HTML + classes gen-1) | **11 primitives + 6 viz** dans `@see/ui` |
| Thèmes | 1 (dark accidentel) | 2 (dark par défaut, light validé AA) |
| Garde-fous | 0 | `ui:check` en CI (couleurs, polices, classes bannies, styles morts) |

## 3. Ce qui reste délibérément hors périmètre

- **Storytelling / animations avancées** : la motion reste utilitaire (`--dur-*`) ; aucune animation d'entrée, aucun micro-parachutisme.
- **Multi-thèmes de marque** : dark + light seulement ; le système supporte l'ajout d'un thème (une couche `themes/*.css`) mais rien n'est prévu pour du white-labeling.
- **Migrer les classes d'écran résiduelles** (`.sandbox-*`, `.chat-*`, `.assumption-*`, `.permission-*`, `.role-row`…) vers des primitives dédiées — elles sont rétokénisées, documentées (`residus-css.md`) et fermées par `ui:check` ; leur conversion en composants (`Chat`, `DataGrid`, panel sandbox) est un chantier produit, pas un chantier système.
- **Bordures au repos à 3:1** (WCAG 1.4.11) : en dessous du seuil en dark ; les champs sont identifiables par leur fond en creux + focus accent. Correctif possible (éclaircir `--line-0`) mais visible sur tout l'app — à arbitrer en phase produit.
- **Re-simulation Viénot de la palette light** : teintes identiques au dark (assombries), attribution inchangée ; le ΔE 13.6 a été validé sur le dark.
- **Bilan de contraste automatisé** : l'audit est un script ponctuel (`/tmp`), pas une étape CI ; `ui:check` couvre couleurs/polices mais pas les ratios.

## 4. Dettes connues (honnêteté)

1. **Le parcours complet n'a jamais été vérifié de bout en bout en mode graphique** dans cette refonte : sans Rust/sidecar sur la machine de travail, l'app web verrouille sur l'écran Projets (P1-00). Toutes les migrations ont été vérifiées par revue de code + typecheck + captures des écrans accessibles. **À faire impérativement au premier lancement Tauri** : créer projet → interview → brief → hypothèses → simulation → résultats → export, en dark et light.
2. `styles.css` contient encore 73 classes d'écran/shell — volontaire, documentées, gardées sous surveillance par `ui:check` (classe morte = CI rouge).
3. Les captures de régression manuelles restent un diff à l'œil ; `@playwright/test` `toHaveScreenshot` est l'outillage naturel suivant si l'équipe veut un diff automatique.

## 5. Verdict

Le design de l'app vit désormais dans `packages/ui` : une source de vérité, deux thèmes, une grammaire dataviz opposable, une doc lisible, une CI qui refuse la dérive. `styles.css` n'est plus un design — c'est un dossier de pièces résiduelles, inventorier et surveillé.
