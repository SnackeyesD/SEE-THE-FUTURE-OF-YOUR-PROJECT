# Journal des modifications

Toutes les évolutions notables de See The Future sont consignées ici.
Le format suit librement [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
et le versionnage sémantique.

## [Non publié] — 3.0.0

### Ajouté

- Cockpit interactif : hypothèses, événements, surface 2D, recherche d'objectif
  et vue 3D avec repli 2D.
- Simulation progressive reproductible : drafts réactifs, runs finaux de
  5 000 tirages, annulation et reprise.
- Persistance locale : projets, scénarios, runs finaux, versions nommées,
  branches archivables et exports `.simproj`.
- Provenance des hypothèses, panneau « D'où vient ce chiffre ? » et explication
  LLM vérifiée numériquement, avec repli déterministe hors ligne.
- Projet d'exemple `retail-depot-brazzaville` importable, avec branches et
  hypothèses sourcées.
- Dossier de pitch Markdown **et PDF**, généré hors ligne à partir d'un run
  final persisté, sans recalcul.
- Parcours guidé local, mémorisé par projet et non bloquant.
- Diagnostic local exportable, avec masquage des clés, chemins, courriels et
  noms de projets.
- Journal local des erreurs, désactivé par défaut, sans envoi réseau.
- Écran « À propos » : versions, licence MIT, mentions de transparence et
  résumé de confidentialité/CGU.

### Sécurité

- Clés d'API uniquement dans le trousseau du système.
- Aucune télémétrie automatique dans cette version.
- Scripts générés exécutés uniquement après revue humaine et en sandbox.
- Protocole IPC `1.16.0` généré depuis une source unique.

### Corrigé

- `protocol:check` ne signale plus de faux écart sur Windows : les fichiers
  générés sont comparés après normalisation des fins de ligne et déclarés en
  `eol=lf` dans `.gitattributes`.
- Un démontage du cockpit n'émet plus de draft ou de final différé, ce qui
  rendait le test de conservation des axes de surface instable.

### Limites connues

- Signature Windows, installateur Linux et mises à jour signées à finaliser
  avec le porteur du certificat.
- Validation juridique des textes provisoires en attente.
- Test utilisateur « premier résultat en moins de 2 minutes » non encore
  consigné sur la machine de référence modeste.
- Le pack de benchmarks `cg-brazzaville-retail-2026.2` n'est pas encore signé ;
  l'exemple utilise `2026.1`.
