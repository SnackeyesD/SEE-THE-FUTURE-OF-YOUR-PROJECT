# Validation utilisateurs — V3

> Journal des tests utilisateurs aux jalons A, B et D. Un test = 20 minutes, sans aide, avec 3 à 4 personnes du public visé.

---

## Protocole

**Profil** : porteur de projet ou gérant de commerce, non familier de l'outil.

**Préparation**

- Profil vierge ou projet d'exemple selon le jalon.
- Aucune explication préalable au-delà de « voici l'application ».
- Enregistrement (avec accord) ou prise de notes à deux personnes : une qui guide, une qui observe.

**Tâches**

1. Décrire son projet et ouvrir une simulation.
2. Lire le point mort et expliquer ce que signifie la fourchette.
3. Tester une hypothèse : « et si je baisse mon prix de 10 % ? »
4. Ajouter un imprévu (hausse fournisseur ou perte de client).
5. (Jalon B) Demander « je veux le point mort en 6 mois » et réagir au résultat.
6. (Jalon D) Exporter un dossier et expliquer ce qu'il contient.

**Mesures**

| Mesure | Définition |
|---|---|
| Temps jusqu'au premier résultat | Ouverture → premier écran de résultats |
| Tâches réussies sans aide | /6 |
| Points de confusion | Verbatim + capture |
| Compréhension de l'incertitude | Peut expliquer P10–P90 et la graine |
| Confiance | « Feriez-vous confiance à ce chiffre ? » (1–5) |
| Intention | « Utiliseriez-vous l'outil pour votre projet ? » (1–5) |

---

## Session — Jalon A (phase 09)

- Date :
- Participant (anonyme) :
- Appareil / OS :
- Durée :

### Observations

| Étape | Temps | Réussi | Verbatim / confusion |
|---|---|---|---|
| … | | | |

### Constats

1.
2.

### Décisions

- [ ] Aucun changement
- [ ] Ajustement UI (phase 09)
- [ ] Réordonnancement du plan (§7)

---

## Session — Jalon B (phase 11–12)

_(même grille)_

---

## Session — Jalon D (phase 16)

_(même grille, inclure installation et export)_

### Parcours imposé (sans aide)

1. Installer l'application sur une machine où elle n'a jamais été lancée.
2. Ouvrir le projet d'exemple `retail-depot-brazzaville` depuis **Projets**.
3. Ignorer ou suivre le parcours guidé, puis vérifier une hypothèse.
4. Lancer un calcul **final** (5 000 runs) et attendre le premier écran de
   résultats.
5. Expliquer à voix haute ce que signifient P10–P90 et la probabilité de perte.
6. Exporter le dossier Markdown, puis le PDF.
7. Ouvrir **Réglages**, exporter le diagnostic et expliquer ce qu'il contient.
8. Désactiver le réseau et vérifier qu'un nouveau calcul reste possible.

### Critères de réussite du jalon D

| Critère | Seuil |
|---|---|
| Installation sans invitation administrateur surprise | oui |
| Lancement applicatif | < 10 s |
| Premier résultat | < 2 min |
| Tâches réussies sans aide | ≥ 5 / 8 |
| Explication correcte de P10–P90 | oui |
| Aucun secret ni chemin local dans les exports | oui |
| Confiance déclarée | ≥ 3 / 5 en médiane |
| Intention d'usage | ≥ 3 / 5 en médiane |

Consigner les verbatims, les captures et les écarts dans la grille ci-dessus.
Les échecs bloquants (installation, export, hors ligne) passent en correctif
avant la release ; les confusions mineures deviennent des tâches de la phase 16.

---

## Synthèse

| Constat | Fréquence | Impact | Action | Phase |
|---|---|---|---|---|
| | | | | |
