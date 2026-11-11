# DESIGN.md — Le système « Ink & Signal »

> Ce document est la loi visuelle du projet. Il est lisible par un contributeur
> externe : il doit en sortir en sachant **quoi utiliser, où, et pourquoi**.
> Version courte opérationnelle : `packages/ui/README.md`.

---

## 1. Les principes (pourquoi ça ressemble à ça)

### 1.1 Encre neutre, couleur = signal
L'application est un **outil de simulation de décisions** : les chiffres sont le
contenu, l'interface est le support. D'où :

- des fonds **encre** neutres et profonds (`--ink-0` → `--ink-3`), jamais de
  dégradé décoratif, jamais de couleur d'ambiance ;
- la couleur n'apparaît que comme **signal** : `--accent` (interactif),
  `--ok`/`--warn`/`--danger` (états), `--series-*` (données). Si une couleur
  ne dit rien, elle n'est pas là.

Le pendant light (« papier ») applique la même logique inversée : `#eef1f6`
froid, blanc réservé aux surfaces élevées, signaux assombris pour l'AA.

### 1.2 L'accent est interactif — point final
`--accent` (#22d3ee dark / #0d6e89 light) marque **uniquement** ce qui se
clique, se focus ou progresse. Il n'est JAMAIS une couleur de série de données
ni une couleur d'état. Cette règle évite le piège classique des dashboards
(« le bleu est-ce un bouton ou une métrique ? »).

### 1.3 Mono pour les données (R4)
Toute valeur mesurée ou comparée est en `--font-data` (JetBrains Mono) avec
`tabular-nums` : les colonnes s'alignent, les chiffres ne « bougent » pas au
rafraîchissement. Les libellés restent en `--font-ui` (Inter).

### 1.4 Messages actionnables (principe Snyk)
- `InlineAlert` **titre obligatoire** qui dit quoi faire (« Clé API refusée » +
  quoi vérifier), pas « Erreur 401 ».
- `EmptyState` propose toujours une action (« Lancer la simulation »).
- Les états vides ne sont jamais un cul-de-sac.

### 1.5 La doc est le produit (principe Supernova)
Le système est documenté, opposable, et **verrouillé par la CI**
(`ui:check`). Un token qui change passe l'audit de contraste ; un composant
naît dans la vitrine (`?showcase`) ; rien n'entre dans l'app hors du système.

### 1.6 La trame
Fond du shell : grille 28px (encre claire sur dark, encre sombre sur light) —
l'ambiance « plan de données » façon Observable/Hex. **Jamais** sur les zones
de lecture dense (narration, tables longues).

---

## 2. Les couches (de bas en haut)

```
primitives (--ink-*, --line-*, --text-0/1/2)   → ne s'utilisent pas directement
sémantiques (--bg-*, --border, --text, --muted) → consommées par les composants
signaux (--accent, --ok/warn/danger + alphas)   → sémantiques aussi
dataviz (--series-1..10 + fills + --chart-*)    → grammaire viz
code (--code-*) / trame / typo / espace / formes / motion
```

Le thème light redéfinit **uniquement** sémantiques, signaux, séries, code,
trame, ombres — la structure ne bouge jamais.

## 3. Quelle primitive pour quel besoin

| Besoin | Primitive | Notes |
|---|---|---|
| Surface de contenu | `Card` + `CardHeader` | `eyebrow` = signal d'accroche, `title` |
| Action | `Button` (primary/secondary/ghost/danger) | danger ≠ ghost |
| Statut court | `Badge` (5 tons) | jamais couleur seule, toujours un texte |
| Message à décision | `InlineAlert` (title + action optionnelle) | 4 tons |
| Saisie | `Field` / `SelectField` / `TextareaField` | `hint` actionnable |
| Valeur mise en avant | `Stat` (+ `unit`) | mono tabulaire automatique |
| Données tabulaires | `Table` | colonnes `mono: true` pour les chiffres |
| Onglets | `Tabs` (clavier ←/→/HOME/END) | |
| État vide | `EmptyState` | avec action |
| Graphique | `viz/*` | agrégats en entrée, `aria-label` obligatoire |

Les classes CSS d'écran restantes (`styles.css`) sont listées et justifiées
dans `refont/05-ecrans-parcours/residus-css.md`.

## 4. Choisir une série de données

1. L'attribution est **stable par entité** (un scénario garde sa couleur partout).
2. Ordre par défaut : série 1, 2, 3…
3. Les percentiles : P50 seul coloré (série 1), P10/P90 neutres.
4. Teintes identiques dark/light (luminosité adaptée) : un scénario « bleu »
   reste « bleu » quand on bascule de thème.
5. Validité daltonisme : paire la plus proche ΔE 13.6 ≥ 12 (Viénot, phase 02).

## 5. Contribuer (le parcours d'un changement visuel)

1. **Lire** `packages/ui/README.md` (court) puis ce document si arbitrage.
2. **Tokens d'abord** : une valeur nouvelle ou modifiée vit dans
   `tokens.css` (+ son pendant light). Jamais dans un composant.
3. **Primitives ensuite** : styles dans `primitives.css`, React dans
   `components.tsx`, export `index.ts`, variante dans la vitrine.
4. **Vérifier** : focus visible, états vide/erreur, dark et light
   (`npm run dev:web`, captures), puis `npm run typecheck && npm run test && npm run ui:check`.
5. **Écrans** : composent avec les primitives ; un style d'écran résiduel
   doit être documenté dans `residus-css.md` et justifié.

## 6. Pourquoi ces références

- **Snyk** (design docs publiques) : la sobriété développeur, messages
  actionnables, la couleur comme signal — la référence la plus proche de
  notre audience (devs qui lisent des logs et des chiffres).
- **Supernova** : « la doc est le produit », tokens gouvernés, garde-fous CI.
- **Observable / Grafana / Hex** : l'ambiance « console de données » — trame,
  mono, densité maîtrisée, outils qui respirent la mesure plutôt que le SaaS.
- **Nord / Grommet / Workbench** : l'accessibilité et la cohérence comme
  propriété du système, pas comme couche finale (phase 06).

## 7. Garde-fous (ce que la CI refuse)

`npm run ui:check` (intégré au `lint`, lancé dans le job `web`) échoue si :

- un hex/`rgb()` est écrit hors `tokens.css` / `themes/` / `tokens.ts` généré ;
- une police littérale est référencée hors tokens ;
- une classe composant gen-1 bannie réapparaît dans `styles.css`
  (`.card`, `.badge`, `.button--*`, `.tabs`, `.form-*`, `.facts`, `.log*`,
  `.hint`, `.error`, `.muted`, `.ok`, `.actions`…) ;
- une classe de `styles.css` n'est référencée nulle part dans le TSX
  (style mort → purge ou documentation).
