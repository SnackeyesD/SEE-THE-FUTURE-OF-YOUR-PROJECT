# Refonte graphique — « Console de données »

> Plan maître de la refonte design de **See The Future**. Objectif : passer d'une esthétique SaaS générique (bleu/violet classique) à une identité visuelle **orientée données**, qui évoque les jeux de données, la dataviz et les outils centrés développeurs.

---

## 1. Diagnostic (pourquoi refondre)

L'état actuel (`apps/desktop/src/styles.css`, 1528 lignes) :

- **Palette générique** : bleu `#4f8cff` + bleu nuit `#0b1220` + gradients radiaux — un look « startup SaaS » standard qui ne raconte pas le produit (simulation, probabilités, jeux de données).
- **Un seul fichier CSS monolithique** : tokens implicites (`:root`), pas de source de vérité documentée, composants dupliqués (`.card` vs `.ui-card`, `.button` vs `.ui-button`).
- **Typographie orientée OS** : Segoe UI (Windows) + Cascadia Code — pas de police embarquée, rendu différent selon l'OS.
- **Charts maison** (SVG) : palette de 2–3 couleurs seulement, aucune identité dataviz (pas de grille fine, pas de séries différenciées, pas de références visuelles aux données).

## 2. Direction artistique : « Ink & Signal »

Une ambiance **console de données** : fond encre neutre, signaux colorés vifs réservés aux données, typographie monospace pour tout ce qui est chiffre/mesure, trames de grille discrètes.

Inspirations explicitement utilisées :

- **[A developer-centric approach — Snyk](https://snyk.io/blog/developer-centric-approach/)** : outils qui simplifient, messages **actionnables** (dire exactement ce qui ne va pas et quoi faire), intégration transparente, autonomie de l'utilisateur.
- **[8 developer-centric design systems — Supernova](https://www.supernova.io/blog/8-developer-centric-design-systems-to-inspire-your-development)** : tokens comme **source de vérité unique dans le code**, documentation intégrée, automatisation (sync design ↔ code), librairies de référence (Stacks, Nord, Grommet, Workbench) pour la structure et la rigueur.

Ambiance visuelle cible (références produits) : **Observable, Grafana, Hex, Linear** — sombre, neutre, précis, avec des séries de données colorées qui « parlent ».

## 3. Les 7 phases

| # | Phase | Objectif | Dépend de | Livrable clé |
|---|---|---|---|---|
| 01 | [Audit & inventaire](01-audit-design/README.md) | État des lieux complet : écrans, composants, tokens implicites | — | Rapport d'audit + inventaire exhaustif |
| 02 | [Fondations & tokens](02-fondations-tokens/README.md) | Nouveau système de design : palette données, typo, espacements, dark/light | 01 | `tokens.css` + `tokens.ts`, source de vérité unique |
| 03 | [Composants de base](03-composants-base/README.md) | Librairie unifiée (boutons, champs, badges, cartes…) dans `packages/ui` | 02 | `packages/ui` v1 complète, documentée |
| 04 | [Dataviz](04-dataviz/README.md) | Système de séries de couleurs, charts, tables, mesures | 03 | Palette de séries + charts refondus |
| 05 | [Écrans & parcours](05-ecrans-parcours/README.md) | Refonte des 7 écrans + panels avec le nouveau système | 04 | App 100 % migrée visuellement |
| 06 | [Qualité & accessibilité](06-qualite-accessibilite/README.md) | Contraste WCAG, focus, dark/light, cohérence, tests visuels | 05 | Rapport d'accessibilité + screens de régression |
| 07 | [Adoption & nettoyage](07-adoption-nettoyage/README.md) | Suppression de l'ancien CSS, doc d'usage, garde-fous | 06 | `styles.css` délégué au système, doc DESIGN |

## 4. Séquencement et jalons

```
Phase 01 ─▶ Phase 02 ─▶ Phase 03 ─▶ Phase 04 ─▶ Phase 05 ─▶ Phase 06 ─▶ Phase 07
   audit      tokens      base         dataviz      écrans        qualité      adoption
              └───────────┴─── J1 : le système est visible dans un navigateur
                                    └───────┴──── J2 : dataviz + écrans = produit reconnaissable
                                                   └─────────────┴── J3 : conforme, propre, documenté
```

**Jalons**

- **J1 — Le socle vit** (fin phase 03) : les tokens et la librairie de base sont utilisables et visibles sur un écran réel, pas une maquette.
- **J2 — L'identité data est là** (fin phase 05) : un utilisateur reconnaît l'app comme « un outil de données », pas comme une énième app SaaS.
- **J3 — Fondations solides** (fin phase 07) : accessibilité conforme, ancien code supprimé, système documenté pour que toute future UI s'y appuie.

## 5. Principes directeurs (règles à respecter dans chaque phase)

1. **Le design vit dans le code.** Les tokens sont la source de vérité, versionnés, pas un PDF ni une maquette morte.
2. **La couleur est réservée aux données et aux états.** Un fond neutre, des signaux colorés uniquement là où ils portent du sens (séries, ok/warn/danger, accent interactif).
3. **Tout chiffre est en monospace à chiffres tabulaires.** Tabular-nums partout où une valeur est mesurée ou comparée.
4. **Messages actionnables** (Snyk) : une erreur dit quoi corriger, un état vide dit quoi faire ensuite, un résultat dit comment le lire.
5. **Migration incrémentale** : chaque phase doit laisser l'app **fonctionnelle** — jamais de « big bang » qui casse `npm run dev` pendant des jours.
6. **Un seul chemin** : pas de composant hors de `packages/ui` (sauf composant 100 % local à un écran), pas de couleur hex hors de `tokens`.

## 6. Décisions à trancher avant la phase 02

| Décision | Recommandation | Justification |
|---|---|---|
| Police UI | **Inter** (embarquée via `@fontsource/inter`) | Constance cross-OS, unifiable, standard des outils data |
| Police données | **JetBrains Mono** (embarquée) | Chiffres tabulaires excellents, ambiance console |
| Thème | **Dark par défaut + light en phase 06** | L'ambiance data est d'abord sombre ; le light arrive proprement grâce aux tokens |
| Implémentation | **CSS natif + custom properties** (pas de Tailwind ni CSS-in-JS) | Coller au code existant, zéro dépendance, Tauri-friendly |
| Palette de séries | **10 couleurs catégorielles testées daltonisme** (phase 04) | Les simulations comparent des scénarios, il faut différencier |
| Storybook | **Non pour l'instant** (doc intégrée dans `packages/ui`) | Éviter l'over-engineering à ce stade ; une page de démonstration suffit |
