# Phase 06 — Qualité & accessibilité : durcir le système

> Objectif : transformer « ça a l'air bien » en « c'est conforme et réglé ». Contraste WCAG, thème light généré depuis les tokens, cohérence fine, tests de régression visuelle.

---

## 1. Objet

Les systèmes développeur-centrés de référence (Nord, Grommet, Workbench) le disent tous : l'accessibilité et la cohérence ne sont pas une couche finale, mais une propriété du système. Cette phase **vérifie et corrige** avant l'adoption (phase 07), pour ne jamais avoir à refaire.

## 2. Tâches

### 2.1 Audit de contraste (WCAG 2.1 AA)
- Vérifier **chaque paire texte/fond** du système : `--text-*` sur `--ink-*`, états (ok/warn/danger) sur leurs fonds, labels de charts sur fond transparent.
- Corriger les valeurs de tokens qui échouent (ajuster `--text-1`, `--text-2`, les opacités de séries) — jamais la couleur d'un composant individuellement.
- Documenter les ratios dans `refont/06-qualite-accessibilite/contraste.md` (tableau token → ratio → statut).

### 2.2 Thème light (grâce aux tokens, il est presque gratuit)
- Créer `packages/ui/src/themes/light.css` redéfinissant uniquement les **tokens sémantiques** (`--bg-root`, `--bg-surface`, `--border`, `--text`, séries assombries pour rester lisibles).
- Les séries dataviz ont leurs variantes dark/light (plus claires sur light, plus saturées sur dark) — l'attribution par entité reste identique.
- Bascule : setting persisté + `data-theme` sur l'élément racine ; dark par défaut.
- Re-vérifier le contraste sur le thème light (mêmes règles).

### 2.3 Accessibilité interactive
- Focus visible **partout** (token `--focus` partagé) ; tab-order correct sur les écrans clés (Interview, Résultats, Sandbox).
- Charts : accessibles au clavier (légende focusable, lecture du tooltip par focus), `role="img"` + `aria-label` descriptif sur chaque chart.
- Motion : respecter `prefers-reduced-motion` (progressions, transitions).
- Vérifier les états non-couleur : danger/ok/warn ont toujours un texte ou une icône en plus de la couleur (daltonisme + contraste).

### 2.4 Cohérence fine (le « dernier 5 % »)
Passe systématique :
- Rayons cohérents (échelle de tokens, pas de valeurs libres).
- Densités : padding des listes/tables homogènes ; tailles de titres selon l'échelle typo uniquement.
- Trame de fond : identique sur tous les écrans, absente des zones de lecture dense.
- Transitions : uniquement les durées tokenisées.

### 2.5 Régression visuelle
- Capturer la vitrine (phases 02–03) et les écrans clés (Projects, Interview, Résultats) dans dark + light.
- Stocker les références dans `refont/06-qualite-accessibilite/regression/` et noter la méthode de comparaison (simple : captures nommées + diff manuel ; option outillage ultérieur).

## 3. Livrables

| Livrable | Emplacement |
|---|---|
| Rapport de contraste | `refont/06-qualite-accessibilite/contraste.md` |
| Thème light | `packages/ui/src/themes/light.css` |
| Liste des correctifs a11y | `refont/06-qualite-accessibilite/correctifs-a11y.md` |
| Captures de régression | `refont/06-qualite-accessibilite/regression/` |

## 4. Critères de validation (DoD)

- [ ] 100 % des paires texte/fond conformes AA (≥ 4.5:1 texte, ≥ 3:1 grand texte).
- [ ] Le thème light est complet : aucun écran ne casse visuellement en light.
- [ ] Navigation clavier complète sur Interview et Résultats ; charts annotés (`aria-label`).
- [ ] `prefers-reduced-motion` respecté.
- [ ] Aucune information portée uniquement par la couleur.
- [ ] Captures dark/light de référence archivées.

## 5. Dépendances

- Phase 05 (écrans migrés — inutile de durcir du code qui va changer).

## 6. Durée indicative

**2 à 3 jours.**
