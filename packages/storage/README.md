# `see-storage` — persistance locale (phase 03)

SQLite en WAL, repositories typés, cycle de vie des projets et archives `.simproj`.

## Utilisation

```python
from see_storage import ProjectStore

store = ProjectStore()  # SEE_DATA_DIR ou répertoire de données de l'OS
project = store.create_project("Mon projet", currency="XOF")
store.messages.add(project.id, "user", "Bonjour")
info = store.export_project(project.id, "mon-projet.simproj")
imported = store.import_project("mon-projet.simproj", name="Mon projet importé")
store.close()
```

## Données

- `workspace.db` : base SQLite du workspace, mode WAL, migrations versionnées.
- `results/<projectId>/` : résultats détaillés hors base (JSON gzip via
  `save_run_detail`), référencés par `result_path`.
- `backups/` : sauvegardes créées avant migration ou à la demande (`store.backup()`).
- `*.simproj` : archive ZIP avec `manifest.json`, snapshot `project.db` et `results/`.

Le manifeste contient le format (`see-the-future.simproj`), la version d'archive, la version
de schéma, l'identité du projet, la date d'export et une empreinte SHA-256 par fichier.
L'import refuse les archives inconnues, les schémas plus récents, les chemins traversants,
les empreintes invalides et les fichiers non déclarés.

Aucune clé API n'est persistée : `provider_profiles.keychain_ref` référence le trousseau OS.

## Commandes

```powershell
npm run storage:sync
npm run storage:test
npm run storage:lint
```

## Limites assumées

- Le chiffrement de la base et des archives reste une décision dédiée.
- Les très gros résultats détaillés peuvent être déplacés vers un format colonnaire plus tard
  sans changer le contrat des repositories.
- Le verrou d'instance unique est porté par `ProjectStore` (`workspace.lock`) ; SQLite
  sécurise les accès concurrents locaux via WAL et `busy_timeout`.
