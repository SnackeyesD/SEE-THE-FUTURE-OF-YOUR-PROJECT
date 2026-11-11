# Phase 05 — CSS résiduel documenté

> Principe (décision de phase) : les classes **composants** gen-1 (`.card`, `.badge`, `.button--*`, `.hint`, `.error`, `.facts`, `.log`, `.tabs`, `.form-*`, `label`…) sont **mortes et purgées** de `styles.css` (1135 → ~857 lignes). Ce qui reste se répartit en trois catégories : le shell, les classes d'écran, et le socle global des champs. Chaque entrée liste sa raison d'être et son sort prévu en phase 07.

## 1. Shell (`.app-*`, `.brand*`) — `App.tsx`

| Classe | Rôle | Sort phase 07 |
|---|---|---|
| `.app-shell`, `.app-header`, `.app-header__meta`, `.app-nav`, `.app-nav__item(--active)`, `.app-footer` | Ossature du shell : largeur, nav en pilule, badges d'état | Migrer vers primitives (`ui-nav`?) ou promouvoir en composant `Shell` |
| `.brand`, `.brand__mark`, `.brand strong/span` | Marque « encre + accent » (pas de dégradé, ombre `--shadow-1`) | Idem |

## 2. Socle global des champs — tous écrans

| Sélecteur | Rôle | Sort phase 07 |
|---|---|---|
| `button` (global) | Style de base ; les variantes viennent de `Button` (`ui-button--*`) | Fusionner dans `primitives.css` quand plus aucun `<button>` nu |
| `input, select, textarea` + `:focus` | Champs nus restants : selects/inputs du `.role-row` (ProvidersPanel) et `.assumption-row` (HypothesesScreen) | Disparaît quand ces deux grilles passent sur `Field`/`SelectField` |
| `:root { --bg, --surface, --surface-soft }` | **Indirections legacy** vers les tokens (`--ink-0/1/2`) pour `.sandbox-panel`, `.sandbox-*` | Remplacer les usages par les tokens directement, puis supprimer |
| `body` | Halo encre + trame (identité), `background-size` à 3 calques (halo + trame 2 axes) | À déplacer dans `tokens.css`/`base.css` du package UI |

## 3. Classes d'écran conservées (rétokénisées, 0 hex)

| Classe | Écran(s) | Pourquoi conservée |
|---|---|---|
| `.screen`, `.screen__heading` | tous | En-tête standard (h1 + intro + actions à droite) |
| `.split`, `.split--wide` | Brief, Projects, Simulation, Settings | Grille 2 colonnes asymétrique |
| `.onboarding-grid` | Projects | Grille 3 colonnes des étapes d'entrée |
| `.project-list*` | Projects | Rangées « dataset browser » |
| `.chat-*` (`.chat-card`, `.chat-thread`, `.chat-message(--user/--thinking)`, `.chat-message__role`), `.composer`, `.suggestion-list` | Interview | Bulles + composer ; candidat à une primitive `Chat` en phase 07 |
| `.assumption-list`, `.assumption-row(__label)` | Hypothèses | Grille de specs (5 colonnes) ; à convertir en `Table` ou champs liés |
| `.stat-grid`, `.chart-grid`, `.chart-card(--wide)` | Résultats | Disposition des `Stat`/graphes (`viz/`) |
| `.narration` | Résultats | Bloc de texte produit par l'IA |
| `.permission-*` (`.permission-stack`, `.permission-card`, `.permission-table`, `.permission-row`) | Interview, Settings, Résultats | Diffs/tables de permissions ; candidat `Table` |
| `.details`, `.mini-list` | Sandbox, Settings | Résumés repliables, listes compactes |
| `.list` | ProvidersPanel | Rangées de profils (actions à droite) |
| `.role-list`, `.role-row`, `.role-name` | ProvidersPanel | Grille d'assignation rôles→profils (champs nus volontaires) |
| `.providers`, `.card--wide` | ProvidersPanel | Grille 2 colonnes ; `card--wide` = span pleine largeur sur `Card` |
| `.chat-result` | ProvidersPanel | Encart résultat du test fournisseur (fond `--code-bg`) |
| `.sandbox-*` (overlay, panel, code+coloration, logs, metrics, series, table, audit) | SandboxReviewPanel | Panel modal riche ; le plus gros résidu, cible phase 07 |

## 4. Purge effectuée en phase 05 (mort vérifiée par grep TSX)

`.app`, `.header`, `.eyebrow`, `.subtitle`, `.grid`, `.badge(--ok/--down)`, `.card` + `.card h2`, `.facts (div/dt/dd)`, `.actions`, `.button--secondary/--danger/--ghost`, `.hint`, `.error`, `.tabs`, `.tab`, `.tab--active`, `label` (global), `.form-grid`, `.form-span`, `.form-row (+label/button)`, `.budget-row`, `.field-hint`, `.muted`, `.ok`, `.error-inline`, `.log/.log__*`, `.log__list--compact`, `.providers .card--wide` (redondant).

## 5. Leçon de la vague 1

La purge s'est faite **après** vérification grep par classe (les faux positifs `ui-actions`, `app-header`, `role="log"` ont failli faire garder des morts) et **après** migration JSX des derniers consommateurs (`ProvidersPanel` en tête). Ordre à respecter en phase 07 : migrer le JSX d'abord, grep ensuite, couper enfin.
