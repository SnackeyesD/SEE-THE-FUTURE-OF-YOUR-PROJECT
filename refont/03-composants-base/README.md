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

- [x] Les 10 primitives listées existent, typées, sans hex ni px hors tokens.
- [x] Focus visible et navigation clavier vérifiés sur chaque composant (Tab sur la
      vitrine ; ←/→, Home/End sur `Tabs` — script `tabsnav`).
- [x] Aucune valeur dupliquée avec `styles.css` (grep : `--ink`, `--line`, `--signal` uniquement).
- [x] La vitrine montre chaque composant dans tous ses états.
- [x] `npm run typecheck` et `npm test` passent.
- [x] Un écran réel (au minimum : écran Settings) est déjà migré vers la librairie — preuve que ça marche en production, pas seulement en démo.

## 6. Journal de réalisation

### Livré
- **10 primitives + utilitaire densité** dans `packages/ui/src/primitives/` :
  `Button` (4 variants × 2 tailles), `Badge` (5 tons), `Card`/`CardHeader`
  (eyebrow/titre/description/action), `Field`/`SelectField`/`TextareaField`,
  `InlineAlert` (**`title` obligatoire** — principe Snyk), `Stat`, `EmptyState`,
  `ProgressBar`, `Tabs` (roving tabindex, ←/→/Home/End), `Table` (en-têtes mono,
  colonnes `mono:` tabulaires alignées à droite, état vide explicite) ;
  `DensityProvider`/`useDensity`.
- `primitives.css` : styling 100 % tokens (zéro hex), focus visible tokenisé
  `--focus`, `prefers-reduced-motion` géré.
- **Bloc `ui-*` retiré de `styles.css`** (l'ancienne génération 2 migre dans la
  librairie) ; seuls restent 3 sélecteurs descendants gen-1 (`.composer .ui-field`
  etc.) à migrer phase 05.
- `InlineAlert.title` devenant obligatoire : **10 sites d'appel corrigés** avec des
  titres actionnables (« Action impossible », « Exécution impossible »,
  « Échec de l'audit »…).
- **Écran Settings migré** : `.facts` et les deux journaux → primitive `Table` ;
  `formatDateTime` conservé pour l'horodatage.
- **Vitrine `?showcase`** (`ComponentsShowcase.tsx`) : les 10 primitives dans tous
  leurs états, avec rappels de règles. Captures dans `captures/` (vitrine,
  focus-visible, entrée coexistence).
- `conventions.md` : procédure d'ajout de composant, checklist a11y, règle de
  séparation styles.css ↔ librairie.

### Le bug de cascade détecté et corrigé (leçon documentée dans conventions.md §5)
La vitrine capturée fin de phase montrait les **anciennes valeurs** : accent
`#4f8cff`, polices Segoe UI. Deux causes superposées :
1. `tokens.css` : la ligne `--ink-*/--line-*/--text-*` (commentaire d'en-tête)
   contient deux fois la séquence `*/` → le commentaire se referme prématurément
   et le parseur avale tout le `:root` **sans lever d'erreur** (0 règles).
2. `styles.css` redéfinissait aussi `:root { --accent, --border, --text, --muted,
   --ok, --danger }` — importé **après** `tokens.css` dans `main.tsx`, il gagnait
   à la cascade. Ces définitions sont supprimées (un token n'est défini qu'une
   fois, dans `tokens.css`).
Vérification finale par styles calculés : accent `rgb(34 211 238)`,
`--on-accent` `rgb(6 18 26)`, Inter / JetBrains Mono, bordure `--line-0`
`rgb(36 43 56)`, surface `--ink-1` `rgb(16 20 28)`.

### Contrôles de fin de phase
- Grep hex/rgb dans les TSX : **0 occurrence** hors `Charts.tsx` (autorisé,
  traité phase 04).
- Grep hex dans `packages/ui/src/*.css` hors tokens.css : **0 occurrence**.
- `npm test` : verts ; `npm run check -w @see/ui` : `tokens.ts à jour`.

## 6. Dépendances

- Phase 02 (tokens).

## 7. Durée indicative

**3 à 4 jours.**
