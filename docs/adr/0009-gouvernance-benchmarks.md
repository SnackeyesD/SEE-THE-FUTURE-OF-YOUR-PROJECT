# ADR 0009 - Gouvernance des benchmarks locaux signés

- Statut : accepté
- Date : 2026-11-12
- Contexte : phase 08, références de marché pour l'agent et l'écran Hypothèses

## Décision

Les benchmarks sont des fichiers JSON locaux, sourcés, datés, versionnés et signés
Ed25519. Ils fournissent des valeurs de marché indicatives ; ils ne produisent jamais
de résultat de simulation. Le moteur reste la seule source des chiffres simulés.

### Schéma et contenu

- Un pack décrit son identité (`id`, `name`, `version`, `publishedAt`), sa zone
  (`country`, `region`, `regionGroup`), son secteur, sa devise, son éditeur, sa licence
  et son panier de référence éventuel.
- Chaque valeur porte un indicateur canonique en `snake_case`, une unité, une devise,
  une source, une URL, une date de source, une fiabilité et des bornes optionnelles.
- Les fiabilités autorisées sont `official`, `study`, `field` et `estimate`.
- Un pack ne peut pas contenir deux valeurs pour le même indicateur, pays, région,
  secteur et sous-secteur.
- Toute valeur non issue d'une source publique doit être explicitement marquée
  `estimate` et documentée dans `notes`. Aucune valeur inventée ne doit être présentée
  comme officielle.

### Signature et clés

- La signature est détachée, dans un fichier `<pack>.sig`, et couvre les octets exacts
  du fichier JSON.
- La clé privée reste hors du dépôt, sous le profil utilisateur, et n'est jamais
  journalisée, stockée en base ou transmise au sidecar.
- Seule la clé publique est versionnée dans `data/benchmark-packs/keys/public.json`.
- Les clés sont identifiées par `keyId` et peuvent être retirées (`retired`) sans
  invalider les anciennes signatures tant que la politique l'autorise.

### Chargement et lookup

- Le sidecar charge les packs utilisateur puis les packs embarqués, vérifie la
  signature et ignore les packs invalides en conservant l'erreur pour l'UI.
- Le lookup est déterministe : pack publié le plus récemment, puis fiabilité, puis
  spécificité géographique, puis date de source, puis version et identifiant.
- La fraîcheur est calculée par rapport à la date du jour : `fresh` jusqu'à 365 jours,
  `aging` jusqu'à 1095 jours, `stale` au-delà.
- Le fallback géographique va de la ville au pays puis à `GLOBAL`. Une valeur d'une
  autre ville n'est jamais réutilisée pour une ville différente sans fallback explicite.
- Les conflits sont signalés par le nombre de candidats non retenus ; l'UI affiche la
  source, la date, la fiabilité, la fraîcheur, le pack et la clé utilisés.

### Import et audit

- L'import vérifie l'extension, la taille maximale (10 Mo), la présence de la signature,
  la clé publique et la validité du schéma avant toute copie.
- Les fichiers sont copiés atomiquement dans le répertoire utilisateur, puis les
  métadonnées et l'événement `installed` ou `replaced` sont enregistrés dans SQLite.
- Un pack importé peut remplacer un pack de même nom et version ; l'opération est
  tracée avec le checksum et le `keyId`.

### Agent et UI

- L'outil agent `get_benchmark` renvoie une valeur signée avec sa provenance complète.
  Il ne transforme pas cette valeur en chiffre de simulation.
- L'écran Hypothèses peut appliquer une référence à une hypothèse, afficher sa
  provenance et permettre à l'utilisateur de repasser en saisie libre.
- Les valeurs de référence sont marquées comme telles ; elles ne sont pas du contenu
  non fiable au sens des résultats web, mais restent des données de marché à valider.

## Conséquences

- Les packs peuvent évoluer sans modifier le moteur ni le protocole de simulation.
- Une compromission de la clé privée impose une rotation et une revue des packs signés.
- Les données publiques peuvent être incomplètes ou anciennes ; la fraîcheur et la
  fiabilité sont donc visibles et utilisées dans le classement.
- Les valeurs `estimate` restent utiles pour démarrer, mais doivent être remplacées par
  les données de l'utilisateur avant toute décision importante.

## Alternatives écartées

- **Valeurs codées en dur dans le moteur** : impossibles à sourcer, dater et révoquer.
- **Téléchargement cloud obligatoire** : contraire à l'usage hors ligne.
- **Signature intégrée au JSON** : modifierait les octets signés et compliquerait les
  outils de vérification.
- **Confiance implicite dans les fichiers locaux** : un pack importé peut être altéré ;
  la signature détachée rend la fraude détectable.
