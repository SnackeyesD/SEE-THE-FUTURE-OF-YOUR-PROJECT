# Phase 03 — Composants de base : librairie unifiée `packages/ui`

> Objectif : fusionner les styles dupliqués (`.card`/`.ui-card`, `.button`/`.ui-button`…) en une **librairie de composants unique** dans `packages/ui`, construite exclusivement sur les tokens de la phase 02.

---

## 1. Objet

Créer la couche composants du design system, dans l'esprit des systèmes de référence (Stacks de Stack Overflow : *« minimiser le CSS custom grâce à un pattern library réutilisable »*, Workbench de Gusto : *« tokens centralisés + composants modulaires »*).

## 2. État des lieux (d'après la phase 01)

Les doublons à fusionner sont connus : `styles.css` contient deux générations (phase « prototype » puis phase « produit 06 ») : `.card` et `.ui-card`, `button` et `.ui-button`, `.badge` et `.ui-badge`, `.error` et `.ui-alert`, etc. La librairie unifiée **remplace les deux**.

## 3. Tâches

### 3.1 Architecture de `packages/ui`

```
packages/ui/src/
├── tokens.css            # phase 02 (source de vérité)
├── tokens.ts
├── index.ts              # exports uniques
├── primitives/           # briques sans logique métier
│   ├── Button.tsx        # variants: primary | secondary | ghost | danger ; sizes: sm | md
│   ├── Field.tsx         # label + input/select/textarea + hint + erreur
│   ├── Badge.tsx         # variants: neutral | ok | warn | danger | accent
│   ├── Card.tsx          # surface + header/action
│   ├── Alert.tsx         # info/ok/warn/danger — messages actionnables
│   ├── Stat.tsx          # valeur en mono tabulaire + label + hint
│   ├── Empty.tsx         # état vide + CTA suggéré
│   ├── Progress.tsx      # determinate + indeterminate
│   ├── Tabs.tsx
│   └── Table.tsx         # table de données (mono tabulaire)
└── cx.ts                 # utilitaire de classes existant
```

Règles d'écriture :
- Chaque composant : **props typées**, styles uniquement via tokens (`var(--*)`), zéro hex, zéro px magique.
- **Accessibilité native** : éléments HTML sémantiques, focus visible, `aria-*` corrects dès le départ.
- Composants **sans dépendance métier** (pas d'IPC, pas de types `protocol`) — réutilisables côté desktop et web.

### 3.2 Garantir l'actionnabilité (Snyk)
Pour chaque composant d'état (Alert, Empty, Field error) : props obligatoires du type
`{ title, description?, action?: { label, onClick } }` — un message qui ne dit pas quoi faire n'est pas un composant valide. C'est l'application directe du principe Snyk : *« donner des messages qui disent exactement ce qui ne va pas et quoi faire »*.

### 3.3 Migration incrémentale
- Les nouveaux composants vivent à côté de l'ancien CSS (les deux cohabitent).
- Écran par écran (phase 05), les usages sont remplacés ; l'ancien CSS n'est jamais étendu (règle : *interdiction d'ajouter une classe à `styles.css`* à partir de cette phase).

### 3.4 Documentation intégrée (Supernova : documentation dans le code)
- Chaque composant a un doc-comment (JSDoc) listant variants, props et cas d'usage.
- La page de démo de la phase 02 est étendue en **vitrine des composants** (playground local) : chaque primitive, chaque état, avec son code d'usage.

## 4. Livrables

| Livrable | Emplacement |
|---|---|
| Librairie de primitives | `packages/ui/src/primitives/` |
| Vitrine des composants | page de démo `dev:web` |
| Convention de contribution | `refont/03-composants-base/conventions.md` (comment ajouter un composant) |

## 5. Critères de validation (DoD)

- [ ] Les 10 primitives listées existent, typées, sans hex ni px hors tokens.
- [ ] Focus visible et navigation clavier vérifiés sur chaque composant.
- [ ] Aucune valeur dupliquée avec `styles.css` (grep : `--ink`, `--line`, `--signal` uniquement).
- [ ] La vitrine montre chaque composant dans tous ses états.
- [ ] `npm run typecheck` et `npm test` passent.
- [ ] Un écran réel (au minimum : écran Settings) est déjà migré vers la librairie — preuve que ça marche en production, pas seulement en démo.

## 6. Dépendances

- Phase 02 (tokens).

## 7. Durée indicative

**3 à 4 jours.**
