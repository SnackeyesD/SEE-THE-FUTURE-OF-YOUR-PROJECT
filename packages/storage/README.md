# `see-storage` — persistance locale (phase 07)

SQLite en WAL, repositories typés, cycle de vie des projets, branches/versions et archives
`.simproj`.

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

## Schéma v6 — branches, versions et runs

- `scenarios.parent_id` / `branch_label` : une branche est un scénario rattaché à un parent.
- `scenarios.version` : compteur d'édition structurelle de la branche.
- `scenario_versions` : snapshots **immuables** d'un scénario, avec `seed` et
  `engine_version`. Supprimer un scénario ne supprime pas ses versions
  (`ON DELETE SET NULL`).
- `simulation_runs.quality` : `final` uniquement en base ; les `draft` sont refusés par le
  repository.
- `simulation_runs.scenario_version_id` : version de référence éventuelle du run.
- `simulation_runs.pinned` : run conservé pour comparaison (fantôme).
- `simulation_runs.status` : `complete`, `failed` ou `cancelled`.

Sémantique :

- **Branche** : évolue, porte un `parent_id` et un `branch_label`.
- **Version nommée** : snapshot immuable ; `restore()` crée toujours une nouvelle branche,
  jamais de destruction.
- **Épinglage** : un run `pinned` n'est jamais purgé.
- **Restauration** : `store.versions.restore(version_id, label=...)`.
- **Idempotence** : un run final est écrit une seule fois ; un même `run_id` est retourné
  tel quel.

## Rétention

- Par défaut : **200 runs** par projet (`DEFAULT_KEEP_LAST_RUNS`).
- Les runs épinglés et ceux liés à une `scenario_version` ne sont jamais supprimés.
- Les 200 runs les plus récents comptent dans la fenêtre ; les protégés plus anciens
  survivent en plus.
- Un résultat sérialisé de plus de **15 MiB** (`MAX_INLINE_RESULT_BYTES`) est écrit hors
  base dans `results/<projectId>/<runId>.json.gz` et référencé par `result_path`.
- `store.prune_runs(project_id, keep_last=200)` purge un projet ;
  `store.prune_all(keep_last=200)` purge tous les projets. Le sidecar appelle `prune_all()`
  au premier accès au store et journalise le nombre supprimé.

## Compatibilité `.simproj`

- L'export écrit `schemaVersion = 6` et inclut branches, versions et runs épinglés.
- L'import accepte les archives v5 : la base extraite est migrée en v6 avant clonage.
- Les archives v7+ sont refusées avec `SchemaTooNewError`.
- Tous les IDs sont remappés à l'import et à la duplication de projet ; les références
  `parent_id`, `scenario_id` et `scenario_version_id` suivent ce remappage.

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
