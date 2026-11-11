# Standard dataviz « Ink & Signal » (phase 04)

Le langage visuel commun de tous les graphiques de l'app. **Opposable** : un
chart qui ne le respecte pas est un bug. Il complète la charte tokens
(`refont/02-fondations-tokens/charte-couleurs.md`) et `conventions.md` (phase 03).

## 1. La palette de séries — la couleur est une information

10 séries catégorielles définies en phase 02 dans `tokens.css`
(`--series-1` à `--series-10`), validées par simulation Viénot
(deuteranopie / protanopie / tritanopie) : paire la plus proche ΔE 13.6
(seuil 12), contraste ≥ 3.2:1 sur encre.

| Série | Nom | Hex | Attribution par défaut |
|---|---|---|---|
| S1 | Bleu | `#4f8ef7` | Scénario de référence / mesure principale |
| S2 | Émeraude | `#2ec47f` | Premier scénario comparé |
| S3 | Ambre clair | `#f6cd45` | Deuxième scénario comparé |
| S4 | Violet | `#ab8ff7` | Séries suivantes (4e courbe…) |
| S5 | Rose | `#f07db8` | idem |
| S6 | Vermillon | `#ef5f45` | idem |
| S7 | Lime | `#c5ea55` | idem |
| S8 | Teal profond | `#0f6b80` | idem |
| S9 | Brique | `#b83a3a` | idem |
| S10 | Olive | `#7a9e4f` | idem |

**Règles opposables :**
1. **L'accent `#22d3ee` n'est JAMAIS une série.** Il marque l'interactif
   (focus, lien, onglet, progression). La seule exception tokenisée est la
   barre neutre de distribution `--chart-bar` (décision phase 02) — à ne pas
   généraliser.
2. **Attribution STABLE par entité** : un scénario garde son index de série
   entre les écrans, les re-rendus et les re-simulations (la graine du moteur
   → même couleur). On n'attribue JAMAIS une couleur par ordre d'affichage ou
   de tri. Via `serieStyle(index)` / prop `seriesIndex`.
3. **Sémantique fixe** : positif = `--chart-positive` (émeraude), négatif =
   `--chart-negative` (vermillon). Jamais l'inverse d'un chart à l'autre.
   Ces deux tokens sont des états, pas des séries d'entités.
4. **La couleur ne porte jamais seule l'information** : légende textuelle
   obligatoire, tooltips texte, labels de percentiles toujours écrits.

## 2. La grammaire commune (`viz/chart.css`)

- **Fond transparent** — le chart vit sur la surface de sa carte ; jamais de
  fond propre au chart.
- **Grille** : hairline 1px horizontale uniquement (`--chart-grid`), aux ticks
  y. Pas de cadre. Axe de base 1px `--chart-axis`, ligne zéro dashée
  `--chart-zero` quand le domaine traverse 0.
- **Ticks et valeurs numériques** : `--font-data` (JetBrains Mono) 10px,
  `tabular-nums`, couleur `--text-2`. *Aucun chiffre en police UI.*
- **Labels textuels** (mois, hypothèses) : `--font-ui` 11px, `--text-1`.
- **Lignes de série** : 2px, jointures et caps ronds. **Points** : 3px avec
  halo `--chart-ring` (encre) — seulement si ≤ 60 points au total.
- **Aires de distribution** : remplissage `--series-N-fill` (12–18 %).
- **Seuils / percentiles** : ligne dashée 1.5px + label mono au-dessus.
  P10/P90 neutres (`--chart-label`) ; **P50 seul prend la série 1** (référence).
- **Barres** : distribution neutre `--chart-bar` ; comparaisons = couleur de
  série pleine à 78 % ; divergentes = `--chart-positive`/`--chart-negative`.
  Hover : `brightness(1.2)`.
- **Interactivité** : tooltips natifs `<title>` (SVG) ; légende interactive
  (boutons `aria-pressed`, cliquer isole une série) dès qu'un chart a > 1
  série ; état « aucune série » explicite.
- **A11y** : chaque SVG `role="img"` + `aria-label` français explicite ;
  focus visible tokenisé sur les boutons de légende.

## 3. Les composants (`@see/ui` → `packages/ui/src/viz/`)

| Composant | Usage | Points clés |
|---|---|---|
| `LineChart` | Courbes multi-séries, aire optionnelle | légende interactive, ticks y auto (`niceTicks`), zéro inclus |
| `Histogram` | Distribution de runs | percentiles dashés, tooltip par bin ( borne inf→sup, N, %) |
| `BarChart` | Comparaison de catégories (scénarios) | couleur de série par catégorie, valeurs mono au-dessus |
| `DivergingBars` | Tornade de sensibilité | tri par impact côté appelant, tooltip riche (corrélation) |
| `Sparkline` | Micro-aperçu inline | sans axes ; la valeur exacte vit dans le `Stat`/`Table` voisin |

Les composants sont **sans dépendance métier** : pas de `@see/protocol`, pas de
formatteur en dur. Les formats (FCFA, %) arrivent en props (`formatX`,
`formatValue`). Le pont app ⇆ viz vit dans `apps/desktop/src/components/Charts.tsx`.

## 4. Performance

Le moteur simule 10 000 runs : **on n'affiche jamais les points bruts.**
Le moteur agrège (histogramme ~34 bins, moyennes mensuelles, top-8 sensibilité)
et les composants reçoivent ces agrégats. `LineChart` désactive les points au-delà
de 60 positions cumulées. Les `<path>` remplacent tout calcul par-élément
superflu ; aucune animation sur les charts (le mouvement est réservé à la
progression, cf. charte motion).

## 5. Comment ajouter un chart

1. Le besoin existe-t-il déjà ? Sinon : composant dans `packages/ui/src/viz/`,
   en suivant `conventions.md` (procédure d'ajout + checklist a11y) — la
   couleur par `serieStyle()`, jamais en dur.
2. Enregistrer l'usage dans la vitrine (`?showcase`, section dataviz) avec des
   données statiques représentatives.
3. Recapturer la vitrine dans `refont/04-dataviz/captures/`.
4. Vérifier : ticks mono tabulaires ? attribution stable ? légende si > 1 série ?
   tooltip ? `aria-label` ?
