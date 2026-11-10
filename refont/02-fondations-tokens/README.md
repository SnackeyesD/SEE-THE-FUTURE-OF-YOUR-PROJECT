# Phase 02 — Fondations & tokens : « Ink & Signal »

> Objectif : définir le nouveau système de design — palette de données, typographies, échelles, thèmes — sous forme de **tokens** stockés dans le code, source de vérité unique.

---

## 1. Objet

Créer l'ADN visuel de la refonte. Cette phase produit des **décisions**, pas encore l'application réelle. Elle est inspirée des meilleures pratiques des systèmes développeur-centrés (Supernova) : *« tokens comme source de vérité unique dans le code »*.

## 2. Direction visuelle : « Ink & Signal »

Le principe : **le fond est encre neutre, la couleur est signal.**

| Rôle visuel | Traitement |
|---|---|
| Fonds | Neutre, presque sans teinte (gris-bleu très sombres, jamais de gradient décoratif) |
| Structure | Trame de grille fine (hairlines), marques de mesure discrètes, ambiance « plan / dataset » |
| Couleurs | Réservées aux **séries de données**, aux **états** (ok/warn/danger) et à l'**accent interactif** |
| Typo UI | Inter — neutre, précise, standard des outils data |
| Typo données | JetBrains Mono + `tabular-nums` — tout chiffre mesuré ou comparé |
| Motion | Discret, utilitaire (progressions, transitions 120–180 ms), jamais décoratif |

Références d'ambiance : **Observable, Grafana, Hex, Linear**.

## 3. Tâches

### 3.1 Créer `packages/ui/src/tokens.css`
Tokens CSS custom properties, organisés par couches :

```css
/* Primitives (ne s'utilisent jamais directement dans les composants) */
--ink-0: #0b0e13;      /* fond racine */
--ink-1: #10141b;      /* surface */
--ink-2: #161b25;      /* surface élevée */
--ink-3: #1e2532;      /* surface la plus élevée */
--line-0: #232a36;     /* bordure standard */
--line-1: #2e3746;     /* bordure forte */
--text-0: #e8ecf4;     /* texte principal */
--text-1: #97a1b4;     /* texte secondaire */
--text-2: #6b7488;     /* texte tertiaire/discret */

/* Sémantiques (c'est ce que consomment les composants) */
--bg-root: var(--ink-0);
--bg-surface: var(--ink-1);
--bg-raised: var(--ink-2);
--border: var(--line-0);
--text: var(--text-0);
--muted: var(--text-1);
--accent: var(--signal-4);   /* cyan — interactif uniquement */
--ok: ...; --warn: ...; --danger: ...;

/* Dataviz : 10 séries catégorielles (détail en phase 04) */
--series-1: #22d3ee;  /* cyan */
--series-2: #8b5cf6;  /* violet */
--series-3: #34d399;  /* émeraude */
--series-4: #f59e0b;  /* ambre */
--series-5: #ec4899;  /* magenta */
/* ... 10 au total, testées daltonisme */

/* Typographie */
--font-ui: "Inter", system-ui, sans-serif;
--font-data: "JetBrains Mono", "Cascadia Code", monospace;
/* échelles de tailles : --fs-11 à --fs-30 */

/* Espacements (échelle 4px) */
--sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px; --sp-5: 24px; --sp-6: 32px;

/* Rayons, ombres, durées de transition, z-index */
```

### 3.2 Créer `packages/ui/src/tokens.ts`
Miroir TypeScript des tokens (généré ou synchronisé avec le CSS) pour les cas où le code a besoin de valeurs (SVG charts, canvas). Régénérable — pas de valeurs copiées à la main des deux côtés, **même discipline que `packages/protocol`**.

### 3.3 Embarquer les polices
- `@fontsource/inter` (weights 400/500/600/700) + `@fontsource/jetbrains-mono` (400/500/600).
- Import dans le CSS de `packages/ui`, fallback system-ui / Cascadia Code.
- Fini la dépendance à Segoe UI : rendu identique Windows/Linux/macOS.

### 3.4 Trame et ambiance « données »
- Écrire le motif de **grille fine** (hairline 1px tous les N px, opacité ~4 %) comme token `--grid-trame` (background-image réutilisable).
- Définir la texture de fond de l'app : encre plate + trame, **suppression des gradients radiaux**.
- Définir les styles « mesure » : règles graduées, points d'axe, tick marks monospace.

### 3.5 Définir les règles d'usage de la couleur
Écrire la charte (dans ce dossier) :
- Un hex n'apparaît que dans `tokens.css` (vérifiable par grep).
- `--accent` = interactif (liens, focus, sélection, CTA primaire). **Jamais** utilisé comme couleur de série.
- Chaque série a un rôle : contraste, lecture, comparaison.
- Règle 60/30/10 : encre ≥ 60 %, surfaces ~30 %, signal ≤ 10 %.

### 3.6 Page de démonstration des tokens
- Une route/page de dev (`dev:web`) affichant : palette, échelles, typo, trame, états — la « palette de contrôle » du système. Elle servira de planche de référence pendant toute la refonte.

## 4. Livrables

| Livrable | Emplacement |
|---|---|
| Tokens CSS | `packages/ui/src/tokens.css` |
| Tokens TS | `packages/ui/src/tokens.ts` |
| Polices embarquées | `packages/ui` (`@fontsource/*`) |
| Charte d'usage des couleurs | `refont/02-fondations-tokens/charte-couleurs.md` |
| Page de démo tokens | visible via `npm run dev:web` |

## 5. Critères de validation (DoD)

- [ ] `tokens.css` et `tokens.ts` couvrent 100 % des valeurs visuelles de l'ancien CSS (auditée en phase 01) — aucun trou.
- [ ] Grep vérifie : aucun hex en dehors de `tokens.css`.
- [ ] Le rendu est identique Windows/Linux (polices embarquées).
- [ ] La page de démo affiche toutes les échelles et les 10 séries.
- [ ] Les tokens sont exposés/exportés depuis `packages/ui` (import unique).
- [ ] L'app existante compile toujours (les tokens peuvent cohabiter avec l'ancien `:root` le temps de la migration).

## 6. Dépendances

- Phase 01 (inventaire des valeurs existantes).

## 7. Durée indicative

**2 à 3 jours.** C'est la phase la plus importante de la refonte : tout le reste en découle.
