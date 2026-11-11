# Phase 04 — Dataviz : le système de séries et la visualisation des données

> Objectif : donner au produit son identité « data ». C'est ici que la couleur devient **information** : une palette de séries qui différencie les scénarios, des charts à l'esthétique Observable/Grafana, des tables de données prores.

---

## 1. Objet

L'application vend de la **simulation** : des distributions, des percentiles, des comparaisons de scénarios. Aujourd'hui les charts (`components/Charts.tsx`, SVG maison) n'ont qu'une couleur et un style générique. Cette phase crée le langage visuel des données.

## 2. La palette de séries « Signal »

10 couleurs catégorielles définies en phase 02 (`--series-1` à `--series-10`), avec règles d'attribution :

| Série | Couleur | Attribution par défaut |
|---|---|---|
| 1 | Cyan `#22d3ee` | Scénario principal / ligne de référence |
| 2 | Violet `#8b5cf6` | Premier scénario comparé |
| 3 | Émeraude `#34d399` | Résultat positif / seuil atteint |
| 4 | Ambre `#f59e0b` | Avertissement dans les données / seuil critique |
| 5 | Magenta `#ec4899` | Second scénario comparé |
| 6–10 | Sky, lime, orange, teal, rose | Jeux multi-séries (ex. distribution par mois) |

Règles :
- **Attribution stable** : une entité garde sa couleur entre les écrans et les re-rendus (graine de simulation = même couleur) — la reproductibilité du moteur (`ADR 0003`) doit se voir dans la couleur.
- **Cohérence sémantique** : positif = émeraude, négatif = rouge/rose, jamais l'inverse entre deux charts.
- **Testées daltonisme** : vérifier la séparabilité de la série (protan/deutan/tritan) avec un simulateur ; réordonner si nécessaire.

## 3. Tâches

### 3.1 Composants de visualisation dans `packages/ui/viz/`
- `LineChart` : lignes multi-séries, area de distribution optionnelle, grille fine, ticks monospace, tooltip/lecture à la souris.
- `Histogram` : barres de distribution, bande de confiance, marquage des percentiles P10/P50/P90.
- `BarChart` : comparaisons de scénarios (séries 2–5), barres positives/négatives différenciées.
- `Sparkline` : micro-ligne pour les listes et les stats (aperçu sans chart complet).
- `DataGrid` : table de données — en-têtes monospace majuscules, chiffres tabulaires alignés à droite, zébrage discret, ligne sélectionnable.

### 3.2 Langage commun des charts
Écrire et appliquer un standard (dans ce dossier) :
- Fond transparent, grille hairline 1px (token), axes sans cadre.
- Ticks et labels en `--font-data`, 10–11px, `--text-2`.
- Lignes 2px, jointures arrondies, points 3px avec halo `--ink-0`.
- Zone de distribution : remplissage de série à 12–18 % d'opacité.
- Seuils : ligne dashée + label d'unité en mono.
- Chaque chart a une **légende interactive** (cliquer pour isoler une série).

### 3.3 Refonte de `components/Charts.tsx`
- Réécrire les charts existants (résultats, sandbox) au-dessus des nouveaux composants.
- Appliquer l'attribution de séries stables par scénario.
- Faire ressortir les chiffres clés : P50, P10–P90 en mono, badges d'unité (FCFA).

### 3.4 Chiffres et mesures partout
- Créer le composant `Measure` (ou étendre `Stat`) : valeur + unité + contexte, toujours en mono tabulaire.
- L'appliquer aux stats, tables, tooltips, logs : *aucun chiffre « décoratif » hors mono*.

## 4. Livrables

| Livrable | Emplacement |
|---|---|
| Composants viz | `packages/ui/src/viz/` |
| Standard dataviz | `refont/04-dataviz/standard-dataviz.md` |
| Charts existants refondus | `apps/desktop/src/components/Charts.tsx` |
| Planche de séries (daltonisme testé) | visible dans la vitrine |

## 5. Critères de validation (DoD)

- [x] Un chart avec **3 scénarios comparés** se lit sans ambiguïté (chacun sa
      couleur, stable entre les rendus) — démontré dans la vitrine `?showcase`
      (LineChart Référence/Optimiste/Pessimiste) + capture
      `captures/linechart-3scenarios.png` ; l'attribution stable est exposée par
      prop `seriesIndex` (l'écran multi-scénarios réel arrive en phase 05).
- [x] Les séries passent le test de séparabilité daltonisme — palette validée
      par simulation Viénot en phase 02 (ΔE min 13.6, seuil 12 ; contraste
      ≥ 3.2:1), rappelée dans `standard-dataviz.md` §1 et planche dans la vitrine.
- [x] Tous les chiffres de l'app (stats, tables, ticks) sont en mono tabulaire.
- [x] Grille, ticks, percentiles : le standard dataviz est appliqué sur tous
      les charts (`viz/chart.css`, grammaire unique).
- [x] Les charts restent performants : ils ne reçoivent QUE des agrégats du
      moteur (bins, moyennes mensuelles, top-8) — jamais 10 000 points bruts ;
      `LineChart` coupe les points au-delà de 60 positions (standard §4).
- [x] Légende interactive fonctionnelle sur chaque chart multi-séries
      (capture `captures/legende-isolation.png` : 2 séries masquées, domaine
      recalculé).

## 6. Journal de réalisation

### Livré
- **Librairie viz** dans `packages/ui/src/viz/` — sans dépendance métier :
  `LineChart` (multi-séries, aire optionnelle, `niceTicks`, zéro inclus,
  légende interactive `aria-pressed`), `Histogram` (percentiles dashés, P50
  seul coloré en série référence, tooltip par bin), `BarChart` (comparaisons,
  couleur de série par catégorie, valeurs mono au-dessus), `DivergingBars`
  (tornade, positif/négatif, valeur placée côté opposé de la barre),
  `Sparkline`, `Legend`, helpers `scale`/`niceTicks`/`serieStyle`.
- **Grammaire commune** `viz/chart.css` : 100 % tokens. La couleur de série
  arrive par custom properties (`--serie-color`/`--serie-fill` posées par
  `serieStyle()`) — **zéro hex dans tout le TSX, y compris `Charts.tsx`**
  (l'exception historique disparaît).
- **`Charts.tsx` réécrit** comme pont protocole → viz : formats métier
  (FCFA compact) en callbacks, série 1 = mesure de référence.
- **`Stat.unit`** (le « Measure » du plan §3.4) : unité rendue dans la mesure
  mono, adoucie.
- Bloc gen-1 `.chart`/`.chart__*` retiré de `styles.css` (0 règle restante ;
  `.chart-grid`/`.chart-card` = layout d'écran, conservés).
- **`standard-dataviz.md`** : palette + 4 règles opposables + grammaire +
  composants + performance + procédure d'ajout.
- Vitrine : planche des 10 séries, LineChart 3 scénarios, Histogram,
  DivergingBars, Sparkline + Stat.unit. Captures dans `captures/`.

### Bugs trouvés et corrigés pendant la phase
1. **Histogram invisible** : hauteur de barre calculée `yAt(count) − base`
   (négatif par construction) → `height: 0`. Corrigé : `base − yAt(count)`.
2. **Collision tornade** : la valeur en bout de bare recouvrait les libellés
   d'hypothèses pour les barres longues. Corrigé : valeur toujours du côté
   opposé de la ligne zéro (sur encre, jamais de chevauchement).
3. `LineChart` : ReactNode dans `aria-label` (string attendue) — nettoyé.

### Contrôles de fin de phase
- Grep hex/rgb TSX : **0 occurrence sur tout le repo** (desktop + ui).
- Probe styles calculés : ticks JetBrains Mono, ligne série 1 =
  `rgb(79 142 247)` (= `--series-1`), unité `ui-stat__unit` mono.
- Légende : 3 boutons, isolation → 1 ligne visible, domaine recalculé.
- Typecheck desktop + ui verts ; `npm test` : 3 pass / 0 fail.

## 6. Dépendances

- Phase 03 (primitives, dont `Stat` et `Table`).

## 7. Durée indicative

**3 à 4 jours.** C'est la phase qui rend le produit **reconnaissable**.
