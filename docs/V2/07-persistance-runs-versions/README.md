# Phase 07 — Persistance, versions & branches

> **Objectif** : faire de la V3 un produit qui ne perd rien : runs finaux seulement, versions nommées, branches comparables, export `.simproj` compatible, et purge maîtrisée.

**Références** : `V3-COCKPIT.md` §5.1–5.2, I9, I12 ; plan maître C5, C11.
**Dépend de** : phase 02 (forme des résultats) ; peut avancer en parallèle de 03–05.
**Débloque** : 08, 13.
**Profil** : intermédiaire Python (migration/repositories) avec revue senior ; 4–5 jours.

---

## 1. Contexte

Le stockage actuel est plat :

- `scenarios` ne connaît ni parent, ni branche, ni version ;
- `simulation_runs` ne distingue pas `draft`/`final`, ne porte pas de version de scénario ni d'épinglage ;
- chaque `project.simulate` écrit le résultat complet dans `result_json` ;
- `.simproj` n'a aucune notion de versions ;
- aucune purge : les runs s'accumulent.

La V3 doit rendre les expérimentations **réversibles et comparables** sans transformer la base en dépotoir.

## 2. Périmètre

**Inclus**

- Migration `0006` : colonnes de branche, table `scenario_versions`, qualité/épinglage des runs.
- Repositories associés (`ScenarioRepository`, `RunRepository`, nouveau `ScenarioVersionRepository`).
- Sémantique : version nommée, restauration non destructive, branche, épinglage.
- Export/import `.simproj` v6 et compatibilité v5.
- Politique de rétention et purge.
- Tests de migration et de round-trip.

**Exclu**

- UI des branches (phase 13).
- Undo/redo (phase 08) : l'historique d'édition reste en mémoire, pas en base.
- Persistance des runs `draft` (interdite).

## 3. Livrables

- [ ] `MIGRATION_0006` et `LATEST_SCHEMA_VERSION = 6`.
- [ ] `scenario_versions` + colonnes `scenarios.parent_id`, `scenarios.branch_label`, `scenarios.version`.
- [ ] `simulation_runs.quality`, `scenario_version_id`, `pinned`, `status`.
- [ ] `ScenarioVersionRepository` (create/list/get/delete).
- [ ] `RunRepository.prune()` et compteur de taille.
- [ ] Export/import v6, lecture v5.
- [ ] Tests de migration et d'export.
- [ ] Documentation du format et de la sémantique.

## 4. Tâches détaillées

### Lot A — Migration 0006

```sql
ALTER TABLE scenarios ADD COLUMN parent_id TEXT REFERENCES scenarios(id) ON DELETE SET NULL;
ALTER TABLE scenarios ADD COLUMN branch_label TEXT;
ALTER TABLE scenarios ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS scenario_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scenario_id TEXT REFERENCES scenarios(id) ON DELETE SET NULL,
    label TEXT NOT NULL,
    scenario_json TEXT NOT NULL,
    seed INTEGER,
    engine_version TEXT,
    created_at TEXT NOT NULL
);

ALTER TABLE simulation_runs ADD COLUMN quality TEXT NOT NULL DEFAULT 'final'
    CHECK (quality IN ('draft', 'final'));
ALTER TABLE simulation_runs ADD COLUMN scenario_version_id TEXT
    REFERENCES scenario_versions(id) ON DELETE SET NULL;
ALTER TABLE simulation_runs ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0;
ALTER TABLE simulation_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'
    CHECK (status IN ('complete', 'failed', 'cancelled'));

CREATE INDEX IF NOT EXISTS idx_versions_project ON scenario_versions(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_project_created ON simulation_runs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_scenarios_parent ON scenarios(parent_id);
```

- [ ] Vérifier que la migration s'applique sur une base v5 réelle (fixture) et qu'elle est idempotente via le mécanisme existant.
- [ ] Sauvegarde automatique avant migration déjà fournie : vérifier qu'elle couvre la v6.
- [ ] Refuser explicitement un `quality='draft'` à l'insertion (défense en profondeur).

### Lot B — Repositories

- [ ] `ScenarioRepository.duplicate(scenario_id, label)` : crée une nouvelle ligne avec `parent_id`, `branch_label`, `version=1`.
- [ ] `ScenarioRepository.update` : incrémente `version` à chaque modification structurelle.
- [ ] `ScenarioVersionRepository.create(project_id, scenario_id, label, scenario, seed)` : snapshot immuable.
- [ ] `ScenarioVersionRepository.list(project_id)` trié par date.
- [ ] `RunRepository.add(..., quality="final", scenario_version_id=None, pinned=False)`.
- [ ] `RunRepository.set_pinned(run_id, pinned)`.
- [ ] `RunRepository.prune(project_id, keep_last=200)` : supprime les runs non épinglés au-delà de la fenêtre, jamais ceux référencés par une version.
- [ ] `ProjectStore` expose les nouveaux repositories.

### Lot C — Sémantique

- [ ] **Version nommée** = snapshot immuable d'un scénario + graine. Restaurer une version **crée une nouvelle branche** (non destructif) ; l'ancienne reste intacte.
- [ ] **Branche** = scénario avec `parent_id` ; le nom affiché est `branch_label` ou `name`.
- [ ] **Épinglage** = run final conservé pour comparaison (fantôme) ; un run épinglé n'est jamais purgé.
- [ ] Une comparaison exige la même graine : le repository renvoie la graine du run, l'UI (phase 13) refuse un mélange.
- [ ] Le `draft` n'entre jamais en base ; le `final` est écrit une seule fois (idempotence par `run_id`).

### Lot D — Export/import `.simproj`

- [ ] Inclure `scenario_versions` et les nouvelles colonnes dans le manifeste.
- [ ] Bump `schemaVersion` de l'archive à 6 ; écrire `LATEST_SCHEMA_VERSION`.
- [ ] Importer v5 → v6 : colonnes par défaut, aucune perte.
- [ ] Refuser une archive v7+ avec un message clair.
- [ ] Remapper les IDs lors d'un import dans un projet existant ou d'une duplication de projet (collisions).
- [ ] Vérifier l'intégrité (FK, orphelins, checksums) après import.
- [ ] Test aller-retour : projet avec versions + branches + runs épinglés → export → import → égalité fonctionnelle.

### Lot E — Rétention et intégrité

- [ ] Politique par défaut : 200 runs finaux par projet, 15 Mo par run maximum (sinon `result_path` externe).
- [ ] Purge au démarrage ou à la demande, avec log du nombre supprimé.
- [ ] `integrity.check` couvre les nouvelles tables et les références.
- [ ] `storage.backup` inclut les versions.

## 5. Contrats

```python
@dataclass(frozen=True)
class ScenarioVersion:
    id: str
    project_id: str
    scenario_id: str | None
    label: str
    scenario: dict[str, Any]
    seed: int | None
    engine_version: str | None
    created_at: str

class ScenarioVersionRepository:
    def create(...) -> ScenarioVersion: ...
    def list(self, project_id: str) -> list[ScenarioVersion]: ...
    def get(self, version_id: str) -> ScenarioVersion | None: ...
    def delete(self, version_id: str) -> None: ...
```

Règles d'API :

- `duplicate` est idempotent ? Non : chaque appel crée une branche ; l'UI passe un libellé unique.
- `prune` ne supprime jamais un run `pinned=1`.
- Les snapshots sont immuables : `delete` seulement, jamais `update`.

## 6. Pièges

- **Ne pas stocker les drafts** « pour l'historique » : la base grossit de façon incontrôlée.
- **Attention aux FK** : supprimer un scénario ne doit pas supprimer ses versions (`ON DELETE SET NULL`).
- **Migration SQLite** : `ALTER TABLE ... ADD COLUMN` avec `REFERENCES` est accepté si la colonne est nullable ; tester sur une vraie base v5.
- **Import** : ne pas réutiliser les IDs bruts, remapper pour éviter les collisions.
- **Restauration** : ne pas écraser le scénario courant ; créer une branche est plus sûr et annulable.
- **Purge** : ne jamais purger un run référencé par un export en cours.

## 7. Tests

- [ ] Migration v5 → v6 sur fixture, données conservées.
- [ ] Colonnes par défaut correctes (`quality='final'`, `pinned=0`, `status='complete'`).
- [ ] Insertion `draft` refusée.
- [ ] Duplication : parent, label, version.
- [ ] Snapshot immuable : modifier le scénario après création ne change pas la version.
- [ ] Restauration : crée une branche, ne détruit rien.
- [ ] Export/import v6 : égalité fonctionnelle.
- [ ] Import v5 : succès.
- [ ] Import v7 : refus explicite.
- [ ] Purge : conserve épinglés et versions.
- [ ] Intégrité après suppression de scénario.

## 8. Critères d'acceptation

- [ ] Une base v2 migre sans perte.
- [ ] Un projet avec branches/versions s'exporte et se réimporte à l'identique.
- [ ] Les drafts ne sont jamais persistés.
- [ ] Les runs épinglés survivent à la purge.
- [ ] Les tests d'intégrité couvrent les nouvelles tables.
- [ ] La phase 13 peut construire le diff et la comparaison sur ces données.

## 9. Performance

- Migration v5 → v6 < 2 s pour 1 000 runs.
- `prune` < 500 ms pour 1 000 runs.
- Export/import : pas de chargement intégral en mémoire au-delà de 100 Mo ; streaming si nécessaire.

## 10. Risques

| Risque | Mitigation |
|---|---|
| Migration destructive | Backup auto + test fixture + transaction |
| Base qui gonfle | Purge, plafond, drafts interdits |
| Perte de versions à l'export | Test aller-retour, manifeste versionné |
| Collisions d'IDs | Remappage systématique |

## 11. Definition of Done

- [ ] Migration 0006 appliquée et testée.
- [ ] Repositories et sémantique documentés.
- [ ] Export/import v6 et compatibilité v5.
- [ ] Politique de rétention en place.
- [ ] ADR 0014 complété avec le modèle retenu.
