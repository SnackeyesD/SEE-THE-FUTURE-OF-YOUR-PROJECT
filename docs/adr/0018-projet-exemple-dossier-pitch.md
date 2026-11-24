# ADR 0018 — Projet d'exemple et dossier de pitch déterministe

- **Statut** : accepté
- **Date** : 2026-11-23
- **Contexte** : phase 15, s'appuie sur les ADR 0011, 0014 et 0016

## Décision

### Le dossier est une donnée dérivée, jamais une source

Un dossier de pitch est reconstruit à partir de faits **déjà persistés** :

- le run **final** enregistré (`simulation_runs`, résultat détaillé gzippé) ;
- son scénario et ses versions nommées ;
- les branches actives du projet ;
- les métadonnées du projet (nom, devise, secteur).

Le service `report.build` ne lance **aucune** simulation et ne recalcule aucun
agrégat. Il assemble un `ReportInput`, le valide par schéma, puis délègue la
mise en forme à `packages/reporting`. Supprimer le fichier exporté ne perd donc
aucune source : le dossier est rejouable à l'identique tant que le run existe.
C'est l'application directe de la distinction entre source de vérité et vue
dérivée (DDIA, chapitres 11–12).

Conséquences :

- les chiffres du dossier sont, par construction, ceux du cockpit ;
- un run `draft` n'est jamais persisté (ADR 0011) et ne peut donc jamais
  produire de dossier ;
- l'export Markdown est **déterministe** à `generatedAt` près ; le test de
  snapshot compare deux appels successifs avec la même date ;
- le rapport n'invente pas de valeur : une donnée absente s'affiche
  « non disponible » ou « non atteint », jamais `0`.

### Le format Markdown précède le PDF

Le premier livrable est un Markdown téléchargeable. Le PDF, s'il est ajouté,
réutilise le même contenu via l'impression de la webview : aucune seconde
chaîne de calcul, aucun moteur PDF propriétaire. Cela garde l'export hors ligne
et sans dépendance lourde.

### Un modèle est une donnée versionnée, importée par copie

`data/examples/<id>/template.json` décrit un projet d'exemple complet : brief,
scénario, branches, événements, graine, sources. Le sidecar :

1. valide **tout** le modèle avant la moindre écriture (schéma `1.0.0`,
   tolérant aux champs inconnus pour permettre l'évolution, DDIA ch. 4) ;
2. crée le projet, le brief validé, le scénario, la version nommée et les
   branches ;
3. en cas d'échec en cours de route, supprime le projet partiellement créé
   (compensation) ;
4. génère toujours de **nouveaux identifiants** : importer deux fois le même
   modèle produit deux projets indépendants. Aucun scénario n'est partagé par
   référence.

Les branches du modèle remplacent explicitement des hypothèses (`overrides`)
puis revalident le scénario obtenu : la variante « Prix -10 % » est une donnée
du modèle, pas un calcul à l'exécution.

### Traçabilité et confidentialité

Le dossier et l'import respectent les règles de l'ADR 0016 :

- aucune clé API, aucun chemin local, aucun historique de conversation ;
- aucune donnée personnelle dans le modèle d'exemple ;
- les sources documentaires du modèle sont conservées dans les métadonnées du
  projet et reprises dans le dossier ;
- la graine, la version du moteur et l'identifiant du run figurent en tête du
  dossier ;
- la mention « simulation basée sur vos hypothèses, pas une prévision
  garantie » est obligatoire.

### Parcours guidé local et facultatif

Le parcours de découverte est un composant autonome, sans IA. Il :

- ne s'affiche que pour un projet issu du modèle d'exemple ;
- est skippable, fermable avec `Échap`, et navigable au clavier ;
- mémorise sa clôture par projet dans `localStorage` ;
- se réinitialise en supprimant la clé `seefuture.tour.<projectId>`.

L'absence de stockage local ne bloque jamais l'application : le parcours reste
simplement fermé pour la session.

### Protocole

Le protocole passe en `1.15.0` avec trois méthodes requêtables :

- `template.list` ;
- `project.createFromTemplate` ;
- `report.build`.

Les types sont générés depuis `packages/protocol/schema/messages.schema.json`.
Les notifications restent hors de `MethodName`, conformément à l'ADR 0011.
