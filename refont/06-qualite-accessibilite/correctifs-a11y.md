# Phase 06 — Correctifs accessibilité & cohérence

> Journal des correctifs appliqués. Principe : le correctif est **dans le système** (tokens, primitives, base), jamais dans un composant isolé.

## 1. Contraste (WCAG 2.1 AA)

- `--text-2` : `#6e7789` → `#828ba0` (échec 3.83–4.29 partout → ≥ 4.55 partout). Impact : labels de mesures discrets, `--chart-label`, `--faint`.
- `--code-gutter` : `#55617c` → `#6f7c99` (3.05 → 4.52).
- `tokens.ts` régénéré. Détail complet : `contraste.md`.

## 2. Thème light

- Nouveau `packages/ui/src/themes/light.css` : **sémantiques + signaux + séries + code + trame + ombres** uniquement ; activé par `[data-theme="light"]`, dark par défaut.
- Nouveau token sémantique `--bg-halo` (halo du shell) : remplace l'usage direct de `--ink-3` dans le `radial-gradient` du `body` (sinon le halo restait encre en light).
- Alias legacy gen-1 (`--bg/--surface/--surface-soft` de `styles.css`) surchargés dans light.css (consommés par `.sandbox-*`).
- Bascule : bouton du footer (« Thème clair/sombre »), persistée `localStorage["sf-theme"]`, `data-theme` posé sur `<html>` (`useTheme` dans `App.tsx`). Import du thème dans `@see/ui` (toujours chargé, inert sans l'attribut).
- Captures : `regression/light-*.png` — primitives, tables, charts, sparklines basculent tous sans correctif par composant (preuve que la couche sémantique tient).

## 3. Accessibilité interactive

- `role="img"` + `aria-label` **déjà présents** sur tous les charts (`BarChart`, `DivergingBars`, `Histogram`, `LineChart`, `Sparkline` — fait en phase 04) ; `Legend` est `role="group" aria-label="Séries du graphique"`.
- `prefers-reduced-motion: reduce` : kill-switch global ajouté à `primitives.css` (durées animation/transition effacées, `scroll-behavior: auto`). Le `ProgressBar` indéterminé retombe sur sa règle `animation: none` existante.
- Focus : `:focus-visible` tokenisé (`--focus` = accent 50%, offset 2px) sur `ui-button`, `ui-tab`, champs ; le `button` global de `styles.css` hérite du focus navigateur sur fond accent (3:1+).
- États non-couleur : tous les `Badge`/`InlineAlert` portent un **texte** (tonalité jamais seule) ; les états ok/warn/danger des tables s'affichent en badges libellés. Aucune information portée uniquement par la couleur dans les primitives ; côté charts, les séries sont toujours légendées par texte.
- Navigation clavier des écrans Interview/Résultats : vérifiée par revue de code (ordre DOM = ordre visuel, aucun `tabIndex` positif, pas de piège). Vérification interactive complète à faire dans Tauri (constat P1-00 : pas d'IPC en mode web).

## 4. Cohérence fine (`styles.css`)

- **121 déclarations** rétokénisées par mapping documenté : `font-size` → `--fs-*` (17→16, 22→20 : alignement sur l'échelle), `border-radius` → `--r-*` (8–11→`--r-3`, 12–14→`--r-4`, 18→`--r-5`), `padding/margin/gap` → `--sp-*` (10–12→`--sp-3`, 14–18→`--sp-4`, 20–24→`--sp-5`, 28–32→`--sp-6`).
- Restants volontaires : 3 micro-gaps de 2–3px (alignement optique intra-label, sous l'échelle 4px) ; dimensions structurelles (largeurs de colonnes, `max-width`, hauteurs de viewport).
- 0 hex, 0 `rgb()` écrit à la main en dehors de `tokens.css` / `themes/light.css`.

## 5. Régression visuelle

- `regression/dark-projects.png`, `dark-vitrine.png`, `light-projects.png`, `light-vitrine.png` (Playwright, 1440×960, `fullPage`).
- ⚠️ Artefact connu des captures `fullPage` : `background-attachment: fixed` fait répéter le fond (halo+trame) sur toute la hauteur — la trame **semble** traverser les cartes alors qu'en rendu réel (viewport, vérifié par probe) les cartes sont opaques et propres. Comparaison dark/light tout de même fiable (artefact identique des deux côtés).
- Méthode de diff : captures nommées + comparaison manuelle côte à côte ; outillage type Playwright `toHaveScreenshot` envisageable en phase 07.
