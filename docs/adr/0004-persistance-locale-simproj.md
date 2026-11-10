# ADR 0004 — Persistance locale SQLite et projets portables `.simproj`

- **Statut** : accepté
- **Date** : 2026-11-08
- **Contexte** : phase 03

## Décision

La persistance locale vit dans `packages/storage` (import `see_storage`) :

- un **workspace SQLite** `workspace.db` par installation, en mode **WAL** ;
- des migrations versionnées dans `schema_migrations` et `PRAGMA user_version`, avec
  sauvegarde automatique avant migration d'une base existante ;
- des repositories typés par agrégat (projets, messages, briefs, scénarios, runs, profils
  fournisseurs, usage, permissions, benchmark packs) ;
- un verrou d'instance `workspace.lock` et un marqueur `workspace.state` permettant de
  détecter une fermeture anormale ;
- les agrégats de simulation restent dans SQLite ; les résultats détaillés volumineux sont
  écrits hors base dans `results/<projectId>/` en JSON gzip et référencés par `result_path` ;
- les secrets ne sont jamais stockés : les profils fournisseurs ne conservent qu'une
  **référence** `keychain_ref` vers le trousseau OS ;
- **SQLCipher n'est pas activé** en phase 03 : le coût d'une dépendance native et la
  gestion des clés seront évalués dans une décision dédiée ;
- l'export portable est une archive ZIP `.simproj` contenant `manifest.json`,
  `project.db` (snapshot autonome) et `results/`, avec une empreinte SHA-256 par fichier ;
- l'import vérifie le format, la version de schéma, les chemins, les empreintes et
  l'absence de fichiers non déclarés avant d'installer le projet ;
- l'initialisation est paresseuse : le sidecar n'ouvre le stockage qu'à la première commande
  projet, et accepte `SEE_DATA_DIR` pour les tests et les environnements packagés.

## Contexte et raisons

- SQLite est disponible dans la bibliothèque standard Python, sans dépendance native
  supplémentaire, et suffit pour un usage mono-utilisateur desktop.
- Le mode WAL avec `busy_timeout` permet plusieurs connexions locales sans corruption.
- Un snapshot SQLite dans l'archive évite de dépendre d'un dump SQL ou d'une version future
  du workspace.
- Les résultats détaillés peuvent grossir ; les séparer de la base garde les listes de
  projets rapides et l'archive lisible.
- Le format ZIP + manifeste + empreintes est inspectable, diffusable et réparable.
- Le stockage ne doit jamais devenir une fuite de clés API : seules des références sont
  persistées.

## Alternatives

- **Un fichier SQLite par projet** : duplication des migrations et fermeture/verrouillage
  plus complexes pour le cycle de vie global.
- **Tout stocker dans la base, y compris les gros résultats** : base et sauvegardes trop
  volumineuses, lectures de listes ralenties.
- **Parquet / pyarrow dès la phase 03** : dépendance lourde pour des agrégats encore
  modestes ; l'export détaillé pourra évoluer sans changer le contrat.
- **Chiffrement applicatif immédiat** : reporté à une décision dédiée (phase ultérieure ou
  ADR spécifique) pour ne pas inventer un format cryptographique non audité.

## Conséquences

- Toute évolution de schéma passe par une nouvelle migration numérotée ; les tests
  d'intégrité et de migration doivent rester verts.
- Les fichiers `results/` sont la propriété du projet : duplication, export, import et
  suppression doivent les déplacer ou les nettoyer atomiquement.
- Le manifeste `.simproj` est versionné indépendamment du schéma SQLite ; une version
  d'archive inconnue ou un schéma plus récent est refusé explicitement.
- La restauration d'une sauvegarde se fait hors ligne, application fermée, puis
  `PRAGMA integrity_check` est rejoué.
