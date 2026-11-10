# Phase 07 — Adoption & nettoyage : le système devient la loi

> Objectif : supprimer le passé, documenter le présent, sécuriser l'avenir. À la fin de cette phase, `styles.css` n'est plus le design de l'app — `packages/ui` l'est.

---

## 1. Objet

La phase finale transforme la refonte en **état normal du projet**. Trois chantiers : purge de l'ancien CSS, documentation d'usage (pour le projet et ses contributeurs), et garde-fous pour que le système ne se dégrade pas.

## 2. Tâches

### 2.1 Purge de l'ancien CSS
- À partir de la liste des résidus (phase 05), supprimer de `styles.css` tout ce qui est remplacé : les deux générations de composants, les gradients décoratifs, les valeurs hard-codées.
- `styles.css` final ne doit contenir que : l'import de `packages/ui`, le reset global minimal, les styles réellement locaux d'écran (documentés, s'il en reste).
- Vérification par grep : `#0b1220`, `#4f8cff`, `#121c2e`… (valeurs de l'audit) n'apparaissent plus nulle part.

### 2.2 Documentation du design system (Supernova : « la doc est le produit »)
Créer `refont/07-adoption-nettoyage/DESIGN.md` + version courte dans `packages/ui/README.md` :
- **Les principes** : encre neutre, couleur = signal, mono pour les données, messages actionnables (Snyk).
- **Les règles d'usage** : quand utiliser quelle primitive, quelle série, quel état ; l'interdiction des hex hors tokens.
- **Comment contribuer** : ajouter un composant (conventions de la phase 03), ajouter un token, tester dans la vitrine.
- **Pourquoi ces choix** : liens vers les inspirations (Snyk, Supernova) et les références d'ambiance (Observable, Grafana, Hex).

### 2.3 Garde-fous dans le code
- Ajouter un test/lint maison (script `ui:check`) qui échoue si :
  - un hex ou `rgb()` apparaît dans `apps/desktop/src` ou `packages/ui` en dehors de `tokens.css` / `themes/`,
  - un nouveau style est écrit dans `styles.css`,
  - une police non tokenisée est référencée.
- Intégrer le script dans `npm run lint` (ou un `npm run ui:check` appelé par la CI existante).

### 2.4 Vérification de bout en bout
- Parcours complet en dark **et** light : créer projet → interview → brief → hypothèses → simulation → résultats → export.
- Le mode navigateur (`dev:web`) et le mode desktop (`npm run dev`) : même rendu.
- Passer les tests de régression de la phase 06 : aucune régression non expliquée.

### 2.5 Bilan de la refonte
Écrire `refont/07-adoption-nettoyage/bilan.md` :
- Ce qui a été livré vs le plan, écarts et raisons.
- Ce qui reste volontairement hors périmètre (storytelling, animations avancées, multi-thèmes de marque…).
- Mesures avant/après : nb de lignes de CSS, nb de valeurs hard-codées, nb de composants réutilisés.

## 3. Livrables

| Livrable | Emplacement |
|---|---|
| `styles.css` purgé | `apps/desktop/src/styles.css` |
| Doc du design system | `refont/07-adoption-nettoyage/DESIGN.md` + `packages/ui/README.md` |
| Garde-fous | script `ui:check` + intégration lint/CI |
| Bilan | `refont/07-adoption-nettoyage/bilan.md` |

## 4. Critères de validation (DoD)

- [ ] Aucune valeur de l'ancien design n'existe dans le code (grep vérifié).
- [ ] `ui:check` est en place et bloque les régressions.
- [ ] La doc DESIGN est lisible par un contributeur externe : il sait quoi utiliser et pourquoi.
- [ ] Le parcours complet passe en dark et light, sur web et desktop.
- [ ] Le bilan est écrit et honnête (écarts documentés).

## 5. Dépendances

- Phases 01–06 (toutes).

## 6. Durée indicative

**2 jours.**

---

## Bilan global de la refonte

**Durée totale estimée : 17 à 23 jours de travail effectif**, sur 7 phases qui laissent l'application fonctionnelle à chaque étape. Le jalon décisif est **J2** (fin phase 05) : si l'app ne se distingue pas encore visuellement comme un outil de données à ce stade, il faut réagir sur la palette ou la direction — pas sur les écrans.
