# Phase 06 — Rapport de contraste (WCAG 2.1 AA)

> Méthode : calcul WCAG 2.1 (luminance relative, `(L+0.05)/(l+0.05)`) sur les **valeurs réelles** de `packages/ui/src/tokens.css` et `themes/light.css`. Script : alphas composés sur leur fond avant calcul. Seuils : **4.5:1** texte normal, **3:1** grand texte / graphiques 2px (WCAG 1.4.11).

## 1. Dark (défaut) — texte sur fonds encre

| Token | ink-0 `#0b0e14` | ink-1 `#10141c` | ink-2 `#161b26` | ink-3 `#1e2431` | ink-inset `#0d1118` | Statut |
|---|---|---|---|---|---|---|
| `--text-0 #e9edf5` | 16.46 | 15.71 | 14.68 | 13.24 | 16.12 | ✅ |
| `--text-1 #9aa3b6` | 7.62 | 7.28 | 6.80 | 6.13 | 7.46 | ✅ |
| `--text-2 #828ba0` *(corrigé, était `#6e7789`)* | 5.66 | 5.40 | 5.05 | 4.55 | 5.54 | ✅ (avant : 4.29/4.09/3.83/4.09/4.20 ❌) |
| `--accent #22d3ee` | 10.69 | 10.20 | 9.53 | — | 10.46 | ✅ |
| `--ok #34d399` | 10.05 | 9.59 | 8.96 | — | 9.84 | ✅ |
| `--warn #fbbf24` | 11.57 | 11.05 | 10.32 | — | 11.33 | ✅ |
| `--danger #f87171` | 6.98 | 6.67 | 6.23 | — | 6.84 | ✅ |
| `--on-accent #06121a` sur `--accent` | 10.48 | | | | | ✅ |

### Signaux sur leurs fonds translucides (composés)

| Paire | Ratio | Statut |
|---|---|---|
| `--ok` sur `--ok-a7`/ink-0 | 9.10 | ✅ |
| `--warn` sur `--warn-a7`/ink-1 | 9.78 | ✅ |
| `--danger` sur `--danger-a12`/ink-1 | 5.70 | ✅ |
| `--accent` sur `--accent-a14`/ink-1 | 7.80 | ✅ |

### Code (sur `--code-bg`)

| Token | Ratio | Statut |
|---|---|---|
| `--code-gutter #6f7c99` *(corrigé, était `#55617c`)* | 4.52 | ✅ (avant : 3.05 ❌) |
| `--code-comment #7fa087` | 6.56 | ✅ |
| `--code-string #d9a66a` | 8.66 | ✅ |
| `--code-keyword #79a8ff` | 7.98 | ✅ |
| `--code-builtin #50c8c8` | 9.40 | ✅ |
| `--code-number #e6a7e8` | 9.96 | ✅ |

### Séries dataviz (ligne 2px, seuil 3:1)

| Série | ink-0 | ink-1 | | Série | ink-0 | ink-1 |
|---|---|---|---|---|---|---|
| s1 `#4f8ef7` | 6.02 | 5.75 | | s6 `#ef5f45` | 5.88 | 5.61 |
| s2 `#2ec47f` | 8.57 | 8.18 | | s7 `#c5ea55` | 14.05 | 13.41 |
| s3 `#f6cd45` | 12.64 | 12.06 | | s8 `#0f6b80` | 3.16 | 3.02 |
| s4 `#ab8ff7` | 7.36 | 7.03 | | s9 `#b83a3a` | 3.41 | 3.25 |
| s5 `#f07db8` | 7.66 | 7.31 | | s10 `#7a9e4f` | 6.28 | 6.00 |

10/10 ✅ (s8/s9 passent avec la marge la plus faible — à surveiller si les encres s'éclaircissent).

## 2. Light — texte sur papier

Palette définie dans `packages/ui/src/themes/light.css`, validée par le même script.

| Token | bg-root `#eef1f6` | bg-surface `#f7f9fc` | bg-raised `#fff` | bg-inset `#e3e7ee` | Statut |
|---|---|---|---|---|---|
| `--text #1a2230` | 14.10 | 15.14 | 15.96 | 12.87 | ✅ |
| `--muted #4a5468` | 6.72 | 7.22 | 7.61 | 6.14 | ✅ |
| `--faint #5d6880` | 4.94 | 5.30 | 5.59 | 4.51 | ✅ |
| `--accent #0d6e89` | 5.14 | 5.53 | — | 4.69 | ✅ |
| `--ok #047051` | 5.39 | 5.79 | — | 4.92 | ✅ |
| `--warn #a54c08` | 5.10 | 5.44 | — | 4.66 | ✅ |
| `--danger #b91c1c` | 5.71 | 6.13 | — | 5.22 | ✅ |
| `--on-accent #fff` sur `--accent` | 5.36 | | | | ✅ |

Séries light (seuil 3:1 sur `--bg-surface` et `--bg-inset`) : 10/10 ✅ (3.24 au pire, s3 sur inset).
Code light : 6/6 ✅ (`--code-keyword #3b5fb8` 4.82 au plus bas).

## 3. Limites connues (documentées, non bloquantes)

- **Bordures standard** (`--line-0 #242b38` sur `--ink-1` ≈ 1.3:1) : en dessous du 3:1 de WCAG 1.4.11 pour les *limites de composants*. Les champs restent identifiables par leur fond en creux (`--bg-inset`) ET leur `:focus-visible` (accent 3:1+) ; le risque est couvert par le focus. Phase 07 pourra éclaircir `--line-0` si on veut la conformité stricte des bordures au repos.
- **Trame de fond sous les fonds translucides** (alerts `a7/a12`) : la trame du body se devine à travers ; lecture non gênée (le texte est dessus à ≥ 4.5:1), et la règle d'usage exclut déjà la trame des zones denses.
- **ΔE 13.6 des séries** a été validé sur la palette dark (Viénot) ; les séries light gardent les **mêmes teintes** (luminosité adaptée seulement), l'attribution par entité est inchangée — une re-simulation Viénot light est un « nice-to-have » phase 07.

## 4. Corrections appliquées (dark)

| Token | Avant | Après | Motif |
|---|---|---|---|
| `--text-2` | `#6e7789` | `#828ba0` | échouait sur tous les fonds (3.83–4.29 < 4.5) |
| `--code-gutter` | `#55617c` | `#6f7c99` | 3.05 < 4.5 (numéros de ligne = information) |

`tokens.ts` régénéré (`npm run generate -w @see/ui`). Aucun composant retouché : le correctif est **dans les tokens**, conformément à la méthode.
