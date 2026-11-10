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

- [ ] Un écran Résultats avec **3 scénarios comparés** se lit sans ambiguïté (chacun sa couleur, stable entre les rendus).
- [ ] Les séries passent le test de séparabilité daltonisme.
- [ ] Tous les chiffres de l'app (stats, tables, ticks) sont en mono tabulaire.
- [ ] Grille, ticks, percentiles : le standard dataviz est appliqué sur tous les charts.
- [ ] Les charts restent performants (test avec 10 000 runs du moteur).
- [ ] Légende interactive fonctionnelle sur chaque chart multi-séries.

## 6. Dépendances

- Phase 03 (primitives, dont `Stat` et `Table`).

## 7. Durée indicative

**3 à 4 jours.** C'est la phase qui rend le produit **reconnaissable**.
