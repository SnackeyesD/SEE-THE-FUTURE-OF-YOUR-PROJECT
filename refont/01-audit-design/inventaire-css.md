# Inventaire CSS — `apps/desktop/src/styles.css`

> Mesures relevées le 10/11/2026 sur le fichier source (1528 lignes). Chaque entrée est vérifiable par `grep` sur le dépôt.

---

## 1. Vue d'ensemble

| Métrique | Valeur |
|---|---|
| Lignes | **1528** |
| Classes définies | **158** |
| Blocs `@media` | **4** (900px ×2, 720px ×2) |
| Couleurs hex uniques | **24** |
| Valeurs `rgb()` uniques (avec alpha) | **26** |
| Générations de design coexistantes | **2** (séparées par le commentaire `/* Phase 06 — interface produit */` ligne 431) |
| Doublons de composants (2 générations) | 6 paires : `.card`/`.ui-card`, `button`/`.ui-button`, `.badge`/`.ui-badge`, `.error`/`.ui-alert`, `.list`/`.mini-list`, `.log`/`.sandbox-*` |

## 2. Tokens implicites (`:root`, lignes 1–13)

10 variables seulement, toutes datant de la génération 1 :

| Token | Valeur | Usage réel | Problème |
|---|---|---|---|
| `--bg` | `#0b1220` | fond racine | bleu très saturé (teinte « hero SaaS ») |
| `--surface` | `#121c2e` | cartes | idem |
| `--surface-soft` | `#17233a` | cartes hautes | idem |
| `--border` | `#243552` | bordures | teinte bleue, contraste faible |
| `--text` | `#e6edf7` | texte principal | OK |
| `--muted` | `#8ea3c3` | texte secondaire | bleuté, ratio à vérifier |
| `--accent` | `#4f8cff` | **surchargé** : interactif + charts + déco + marque | **pas de sémantique** |
| `--ok` | `#3ecf8e` | succès + points de chart | surcharge |
| `--danger` | `#ff6b6b` | erreurs + barres négatives | surcharge |

**Absents** : échelle d'espacement, échelle typo, rayons, ombres, durées, z-index, séries dataviz, thème light, tokens sémantiques ↔ primitives séparés.

## 3. Couleurs hard-codées (hors tokens)

### 3.1 Hex (24 valeurs)

| Catégorie | Valeurs | Lignes |
|---|---|---|
| Décoratif | `#1b2b48` (gradient radial hero, l.22), `#2d5fc4` (gradient marque + progress, l.461/844) | 2 |
| Formulaires/log | `#0c1524` (fonds inputs, listes, logs ×3), `#0a101b`, `#080d17` (sandbox) | 5 |
| Marque | `#fff` (texte boutons/marque ×3) | 3 |
| **Charts — couleurs de données** | `#4f8cff`, `#3ecf8e`, `#f0b45a` (marqueurs P10/P50/P90 dans `Charts.tsx`), `#2d5fc4`, `#3ecf8e` (progress) | 5+ |
| Coloration syntaxique sandbox | `#52657f`, `#6f8b73`, `#d9a66a`, `#79a8ff`, `#50c8c8`, `#e6a7e8`, `#6f84a6` | 7 |
| Autres | `#8db4ff` (badge accent), `#e6edf7`/`#8ea3c3`/`#243552`/`#121c2e`/`#17233a`/`#0b1220`/`#121c2e` (dupliquent les tokens) | 7 |

### 3.2 `rgb()` (26 motifs, souvent répétés)

Les 4 teintes de la génération 1 avec 26 combinaisons d'alpha générées **à la main** :

| Teinte | Alphas utilisés | Équivalent token manquant |
|---|---|---|
| `79 140 255` (accent) | 7, 8, 10, 14, 16, 22, 35, 45, 62 % | `--accent-alpha-*` (9 niveaux !) |
| `12 21 36` (fonds) | 45, 50, 55, 60, 65, 70 % | `--bg-overlay-*` (6 niveaux) |
| `255 107 107` (danger) | 7, 12, 35, 45, 55 % | `--danger-alpha-*` |
| `62 207 142` (ok) | 7, 35, 45, 60 % | `--ok-alpha-*` |
| `240 180 90` (warn) | 6, 7, 35, 40, 45 % | **pas de token `--warn` du tout** |
| `142 163 195` (axes charts) | 30, 45 % | `--chart-axis` |

→ **73 écritures manuelles d'alpha** au total (26 motifs, dont 9 pour la seule teinte accent). Aucun token de transparence ; chaque ajustement visuel exige de retoucher des valeurs à la main à plusieurs endroits.

## 4. Typographie

| Déclaration | Lignes | Problème |
|---|---|---|
| `font-family: "Segoe UI", system-ui, -apple-system, sans-serif` | l.3 (root), l.1193 (labels chart) | dépend OS (Windows-first) ; rendu non reproductible |
| `font-family: "Cascadia Code", "Consolas", monospace` | l.381, l.1199, l.1027, l.1363 | 4 écritures différentes de la même famille |

- Aucune police embarquée ; `Cascadia Code` absent de la plupart des machines Linux.
- Tailles non normalisées : 16 tailles distinctes en px dont 7 demi-pixels (`12.5px` ×6, `11.5px` ×7, `10.5px`, `13px`…) — aucune échelle.

## 5. Gradients décoratifs (5)

| Ligne | Gradient | Rôle |
|---|---|---|
| 22 | `radial-gradient(circle at 20% -10%, #1b2b48 → --bg)` | **hero décoratif** — l'ambiance « startup » à remplacer |
| 89, 549 | `linear-gradient(180deg, surface-soft → surface)` | dégradé de carte (deux copies) |
| 461 | `linear-gradient(145deg, #4f8cff, #2d5fc4)` | logo — déco |
| 844 | `linear-gradient(90deg, #2d5fc4, #4f8cff, #3ecf8e)` | barre de progression arc-en-ciel |

## 6. Cartographie des 158 classes

### 6.1 Par catégorie

| Catégorie | Classes | Note |
|---|---|---|
| Génération 1 — prototype (hors phase 06) | ~65 : `.app`, `.header`, `.grid`, `.card`, `.badge*`, `.button--*`, `.tabs`, `.facts`, `.providers`, `.role-*`, `.form-*`, `.log__*`, `.chat-*` (anciens), `.error`, `.hint`… | consommées surtout par `ProvidersPanel.tsx` et `SettingsScreen.tsx` |
| Génération 2 — produit phase 06 | ~45 : `.ui-*`, `.app-shell`, `.app-nav`, `.screen`, `.split`, `.chart*`, `.narration`… | la majorité des écrans |
| Dataviz | 10 : `.chart__axis/zero/bar/line/point/label/tick` | palette : accent + ok + danger seulement |
| Sandbox | 26 : `.sandbox-*` | panel isolé, cohérent mais séparé du système |
| Morts (confirmées, zéro référence TSX) | **16** : `.app`, `.badge`, `.badge--down`, `.badge--ok`, `.eyebrow`, `.grid`, `.header`, `.subtitle`, `.tab`, `.tab--active`, `.tabs`, `.card--wide`, `.budget-row`, `.button--secondary`, `.button--ghost`, `.button--danger` | ~10 % du fichier |

### 6.2 Consommateurs de la génération 1 (cibles de migration prioritaires phase 05)

| Fichier | Classes gen-1 utilisées |
|---|---|
| `components/ProvidersPanel.tsx` | `.providers`, `.card`, `.form-grid`, `.form-row`, `.form-span`, `.list`, `.actions`, `.hint`, `.error`, `.error-inline`, `.muted`, `.ok`, `.facts`, `.role-row`, `.role-name`, `.role-list` |
| `screens/SettingsScreen.tsx` | `.split`, `.mini-list`, `.facts`, `.log__list`, `.log__list--compact`, `.log__empty`, `.log__line--*`, `.log__time` |
| `screens/InterviewScreen.tsx` | `.chat-*`, `.composer`, `.suggestion-list`, `.permission-card` |
| `screens/HypothesesScreen.tsx` | `.assumption-*` |
| `screens/ProjectsScreen.tsx` | `.onboarding-grid`, `.project-list*` |
| `screens/ResultsScreen.tsx` | `.stat-grid`, `.chart-grid`, `.narration`, `.mini-list` |
| `components/SandboxReviewPanel.tsx` | `.sandbox-*`, `.details`, `.mini-list` |
| `App.tsx` | `.app-shell`, `.app-header`, `.app-nav`, `.brand*`, `.app-footer` |

## 7. Points relevés pour la phase 04 (dataviz)

- `Charts.tsx` définit ses couleurs **en dur dans le TSX** (`#f0b45a`, `#4f8cff`, `#3ecf8e` lignes 36–38) — hors CSS, donc invisibles pour `:root` : cas d'école du manque de source de vérité.
- Une seule couleur de ligne/série (`--accent`) ; aucun mécanisme multi-séries ; impossible de comparer 3 scénarios.
- Pas de grille horizontale, pas de graduations Y, pas de bande de confiance.
- Barres : `fill: rgb(79 140 255 / 62%)` — le même accent bleu que les boutons, la navigation et le logo.

## 8. Points relevés pour la phase 06 (qualité)

- Ratios de contraste à vérifier en priorité : `--muted #8ea3c3` sur `#0c1524` (texte secondaire omniprésent), `--accent #4f8cff` sur `--bg #0b1220` (texte d'eyebrow ~4.1:1), `#8db4ff` (badge accent) sur fond sombre.
- Focus : `outline: 2px solid rgb(79 140 255 / 35%)` sur les inputs seulement ; **aucun focus visible tokenisé** pour les boutons, onglets, éléments de liste cliquables.
- `prefers-reduced-motion` : non traité (animation `ui-progress-slide` l.853).
- États ok/warn/danger portés par la couleur seule dans plusieurs cas (`.log__line--success/--error`, `.ok`/`.error-inline` dans ProvidersPanel).
