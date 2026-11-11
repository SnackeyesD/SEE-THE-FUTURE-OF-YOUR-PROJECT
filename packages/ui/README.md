# @see/ui — Design system « Ink & Signal »

> Ce package EST le design de l'application. Toute surface visuelle passe ici :
> tokens + primitives + dataviz. Un écran n'écrit jamais de style propre.

## Contenu

| Fichier | Rôle |
|---|---|
| `src/tokens.css` | **Source de vérité unique des valeurs** (encres, signaux, séries, typo, espacement, motion). Le seul endroit à hex du système. |
| `src/tokens.ts` | Généré depuis tokens.css (`npm run generate -w @see/ui`). Ne pas éditer. |
| `src/themes/light.css` | Thème clair : redéfinit les tokens sémantiques uniquement (`[data-theme="light"]`). |
| `src/primitives.css` | Les composants de base (`ui-card`, `ui-button`, `ui-field`, `ui-table`, `ui-badge`, `ui-alert`…) — consomment UNIQUEMENT les tokens sémantiques. |
| `src/viz/` | Grammaire dataviz (`LineChart`, `Histogram`, `DivergingBars`, `BarChart`, `Sparkline`, `Legend`) + `chart.css`. |
| `src/components.tsx` | Les primitives React (API et conventions : voir `refont/03-composants-base/conventions.md`). |

## Règles d'usage (les 6 commandements)

1. **Aucun hex, aucun `rgb()` écrit à la main** en dehors de `tokens.css` et `themes/`. Le script `npm run ui:check` (racine) fait échouer la CI sinon.
2. **Les composants consomment les tokens SÉMANTIQUES** (`--bg-surface`, `--text`, `--muted`, `--border`, `--accent`, `--ok`…), jamais les primitives (`--ink-*`, `--line-*`, `--text-0/1/2`).
3. **L'accent `--accent` est INTERACTIF uniquement** : focus, liens, sélection, CTA, onglet actif, progression. Jamais couleur de série de données.
4. **Toute valeur mesurée est mono + tabulaire** : `--font-data` + `font-variant-numeric: tabular-nums` (les composants `Stat`/`Table` le font déjà).
5. **Messages actionnables** (principe Snyk) : `InlineAlert` a toujours un `title` qui dit quoi faire ; `EmptyState` propose toujours une action.
6. **Motion tokenisée** : `--dur-*`/`--ease-*` seulement ; respecter `prefers-reduced-motion` (kill-switch global déjà en place).

## Ajouter un composant

1. Vérifier qu'aucun existant ne couvre le besoin (vitrine : `?showcase`).
2. Créer la primitive dans `src/` : styles dans `primitives.css` (tokens sémantiques seulement), React dans `components.tsx`, export via `index.ts`.
3. Ajouter la variante à la vitrine (`apps/desktop/src/components/ComponentsShowcase.tsx`).
4. Vérifier focus visible, états vide/erreur, dark **et** light.

## Ajouter / modifier un token

1. Éditer `src/tokens.css` (layer correspondant), régénérer : `npm run generate -w @see/ui`.
2. Un changement de valeur doit passer l'audit de contraste (méthode : `refont/06-qualite-accessibilite/contraste.md`).
3. Si c'est une valeur de série : doc `refont/02-fondations-tokens/charte-couleurs.md` (validité Viénot).
4. Le thème light doit être mis à jour en même temps que le dark.

## Doc complète

`refont/07-adoption-nettoyage/DESIGN.md` (principes, arbitrages, comment contribuer).
