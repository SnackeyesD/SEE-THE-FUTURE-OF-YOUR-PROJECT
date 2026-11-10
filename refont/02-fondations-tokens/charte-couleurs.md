# Charte d'usage des couleurs — « Ink & Signal »

> Règles opposables pour tout le code UI de See The Future. Vérifiables par grep et (phase 07) par le script `ui:check`.

---

## 1. Les 5 règles fondamentales

### R1 — Un hex n'existe que dans `tokens.css`
Toute couleur s'écrit `var(--…)`. Exceptions générées, exemptées par construction :
- `packages/ui/src/tokens.ts` (miroir généré depuis `tokens.css` — ne pas éditer)
- `packages/ui/src/themes/*.css` (thèmes alternatifs, phase 06)

Vérification : `grep -rEn '#[0-9a-fA-F]{3,8}' apps/desktop/src packages/ui/src --include='*.tsx'` → zéro résultat.
(L'ancien `styles.css` contient encore des hex : purge complète en phase 07, cf. audit S2.)

### R2 — L'accent est interactif, jamais décoratif ni data
`--accent` (#22d3ee, cyan) réserve à : focus, liens, sélection, CTA primaire, onglet actif, progression. **Jamais** : couleur de série, badge de statut, décoration de fond. C'est ce qui garantit que « ce qui brille = ce qui répond ».

### R3 — La couleur porte un sens ou elle ne s'affiche pas
Fond = encre neutre (`--ink-*`) + trame. Un pixel coloré signifie : une série de données, un état (ok/warn/danger), ou une interaction. Pas de gradient décoratif (les 5 gradients de l'ancienne génération sont condamnés, cf. audit S6).

### R4 — Toute valeur mesurée est en mono tabulaire
`font-family: var(--font-data)` + `font-variant-numeric: tabular-nums` pour : chiffres de stats, ticks de charts, montants, pourcentages, IDs, timestamps. Inter (`--font-ui`) pour la prose et les libellés.

### R5 — Les états ok/warn/danger ne cohabitent pas avec les séries
Les statuts habillent l'**interface** (badges, alerts, logs), les séries habillent les **données** (charts, tables). Teintes proches autorisées, contexte disjoint — jamais un graphique où vert = « ok UI » et vert = « scénario 2 ».

## 2. La palette de séries — validation daltonisme réelle

**Méthode** : simulation de Viénot/Brettel (matrices en RGB linéaire) pour la deuteranopie, la protanopie et la tritanopie ; distance CIE76 en Lab entre chaque paire de séries simulées. Seuil d'exigence : ΔE ≥ 12. Script reproduit dans le dépot de la planche (constat : les matrices **compriment les lightness** — un vert clair et un bleu foncé peuvent devenir quasi identiques sous tritanopie — d'où l'étagement en teintes ET en chroma, pas seulement en clarté).

| Série | Hex | Nom | Contraste sur `--ink-0` |
|---|---|---|---|
| `--series-1` | `#4f8ef7` | bleu — scénario de référence | 6.0:1 |
| `--series-2` | `#2ec47f` | émeraude profonde | 8.6:1 |
| `--series-3` | `#f6cd45` | ambre clair | 12.6:1 |
| `--series-4` | `#ab8ff7` | violet | 7.4:1 |
| `--series-5` | `#f07db8` | rose | 7.7:1 |
| `--series-6` | `#ef5f45` | vermillon | 5.9:1 |
| `--series-7` | `#c5ea55` | lime | 14.0:1 |
| `--series-8` | `#0f6b80` | teal profond | 3.2:1 |
| `--series-9` | `#b83a3a` | brique | 3.4:1 |
| `--series-10` | `#7a9e4f` | olive | 6.3:1 |

**Résultats** : la paire la plus proche sous l'une des trois simulations est **S5+S7 (ΔE 13.6)** — au-dessus du seuil 12. Paires suivantes : S3+S6 (14.3), S6+S7 (14.6), S2+S8 (14.6). Contraste sur fond encre : ≥ 3.2:1 (cible 3:1 pour un tracé de 2px). **Le l'accent (#22d3ee) est exclu du calcul volontairement** (R5 : il ne cohabite jamais avec les séries).

## 3. Règles d'attribution

1. **Stabilité** : une entité garde sa couleur partout (écrans, re-rendus). Clé d'attribution = identité stable (id du scénario, index fixe), jamais l'ordre du tableau courant. API : `seriesColor(index)` / `seriesFill(index)` depuis `tokens.ts`.
2. **Ordre par défaut** : S1 (référence), puis S2…S10. Les comparaisons de scénarios commencent à S2 (S1 = référence/baseline).
3. **Sémantique figée** : positif = émeraude/vert (S2), négatif = rouge (S9), alerte de données = ambre (S3). Jamais l'inverse entre deux charts.
4. **Aires de distribution** : `--series-N-fill` (alpha 14 % ; 18 % pour S8/S9, trop sombres en 14 %). Jamais une couleur pleine en remplissage.
5. **Maximum affiché** : au-delà de 5 séries simultanées, exiger une légende interactive (phase 04) — la couleur ne suffit plus, même validée.

## 4. Ce que la couleur ne fait jamais

- Porter seule une information (toujours un label, une icône ou un texte associé — cf. WCAG 1.4.1, phase 06).
- Signaler un danger par du rouge sur fond non encre (les a-ranges `--danger-a*` existent pour ça).
- Animer : la couleur est statique ; seuls les progrès (barres) et les transitions tokenisées bougent.

## 5. Application pratique (grep exécuté à chaque phase)

| Vérification | Commande | Attendu |
|---|---|---|
| Hex hors tokens | `grep -rEn '#[0-9a-fA-F]{3,8}' apps/desktop/src packages/ui/src --include='*.tsx'` | 0 |
| rgb() hors tokens | `grep -rn 'rgb(' apps/desktop/src --include='*.tsx'` | 0 |
| Consistance tokens.ts | `npm run check -w @see/ui` | « tokens.ts à jour » |

## 6. Historique des choix (pour ne pas redébattre)

- **Accent cyan ≠ bleu de série** : le v1 de la palette avait S1 ≈ accent → abandonné (protanopie : ΔE 3.0, illisible). Résolu en réservant le cyan à l'interaction et en poussant le bleu de série vers #4f8ef7.
- **S10 olive** : les bleus/violets se collaient aux séries froides sous tritanopie ; une teinte chaude désaturée (olive) résout sans surcharger le coin rouge/orange.
- **S9 brique foncée** plutôt que rouge vif : évite la collision avec S6 vermillon sous tritanopie (ΔE 6.5 → 14.3).
- **10 couleurs, pas plus** : au-delà, aucune palette ne reste séparable sous les 3 simulations — le design doit limiter le nombre de séries affichées simultanément.
