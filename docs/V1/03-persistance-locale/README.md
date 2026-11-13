# Phase 03 — Persistance locale & projets portables

> **Objectif** : stocker tout le projet localement dans SQLite, avec migrations, sauvegarde et format portable `.simproj` — et **aucun secret** dans la base.

**Références** : `ARCHITECTURE-DESKTOP.md` §8, §11.

---

## 1. Contexte et dépendances

- **Dépend de** : phases 01 (shell, sidecar) et 02 (schémas de scénario/resultats).
- **Débloque** : phases 05, 06, 08, 09.
- **Principe** : la base est la source de vérité locale ; le fichier `.simproj` est un export autonome.

## 2. Objectifs

1. Base SQLite en mode WAL, migrée et versionnée.
2. Couche d'accès (repositories) testable et indépendante de l'UI.
3. Cycle de vie projet : créer, ouvrir, renommer, dupliquer, archiver, supprimer.
4. Format portable `.simproj` vérifiable (manifeste + empreinte).
5. Stockage des résultats volumineux hors base, mais référencés.
6. Journal d'usage (tokens, coût) et permissions persistées.
7. Chiffrement optionnel et reprise après corruption.

## 3. Périmètre

**Inclus**
- Schéma de base et migrations.
- Repositories : `project`, `message`, `brief`, `scenario`, `simulation_run`, `provider_profile`, `usage_log`, `tool_permission`, `benchmark_pack`.
- Import/export `.simproj`.
- Sauvegarde/restauration et intégrité.
- Stockage des résultats (Parquet/JSON compressé).

**Exclu**
- Sync cloud (phase 10).
- Chiffrement de bout en bout (phase 10 si sync).
- Contenu des benchmarks (phase 08).

## 4. Livrables

- [ ] Module de migration (`user_version` ou outil dédié).
- [ ] Schéma SQL documenté et versionné.
- [ ] Couche repositories + tests.
- [ ] Service `ProjectStore` (CRUD + import/export).
- [ ] Format `.simproj` spécifié et implémenté (zip + manifeste + checksum SHA-256).
- [ ] Commande de sauvegarde et de réparation d'intégrité (`PRAGMA integrity_check`).
- [ ] Option SQLCipher documentée (activée ou non selon décision).
- [ ] ADR stockage local et format portable.

## 5. Tâches détaillées

### Lot A — Schéma et migrations
- [ ] Créer le schéma initial avec clés étrangères, index et contraintes.
- [ ] Activer `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout`.
- [ ] Système de migrations ordonné, idempotent, testé (forward uniquement).
- [ ] Test : base ancienne migrée sans perte.
- [ ] Interdire tout champ de secret par revue de schéma automatisée.

### Lot B — Repositories
- [ ] `ProjectRepository`, `MessageRepository`, `BriefRepository`, `ScenarioRepository`, `RunRepository`, `UsageRepository`, `PermissionRepository`.
- [ ] Transactions pour les opérations multi-tables (ex. création d'un projet + brief).
- [ ] Pagination des messages et des runs.
- [ ] Requêtes typées et testées (pas de SQL dans l'UI).

### Lot C — Cycle de vie projet
- [ ] Créer un projet avec métadonnées (nom, devise, secteur, dates).
- [ ] Ouvrir/fermer, projet récent, verrou d'instance unique.
- [ ] Dupliquer un projet (copie base + résultats).
- [ ] Archiver/supprimer avec confirmation (corbeille plutôt que suppression définitive).

### Lot D — Format `.simproj`
- [ ] Spécifier l'archive :
  ```
  projet.simproj (zip)
  ├── manifest.json        # version, id, nom, dates, checksum
  ├── project.db           # base SQLite du projet
  ├── results/             # Parquet/JSON des runs volumineux
  └── attachments/         # éventuels fichiers importés
  ```
- [ ] Export atomique (fichier temporaire puis renommage).
- [ ] Import avec vérification de version, de checksum et de compatibilité de schéma.
- [ ] Refus explicite d'un fichier corrompu ou d'une version trop récente.
- [ ] Test d'aller-retour : export → import → mêmes données.

### Lot E — Résultats et volumétrie
- [ ] Stocker les agrégats en base, le détail des runs en Parquet/JSON compressé.
- [ ] Nettoyage/rotation des runs détaillés selon un quota.
- [ ] Calcul de la taille du projet et affichage.

### Lot F — Intégrité, sauvegarde, chiffrement
- [ ] Sauvegarde automatique avant migration.
- [ ] `PRAGMA integrity_check` au démarrage si fermeture anormale.
- [ ] Mécanisme de récupération (base de secours, export d'urgence).
- [ ] Évaluer SQLCipher : coût, disponibilité, impact performance ; décider et documenter.
- [ ] Aucune clé API : vérifier par test automatisé que le mot `key`/`token` n'apparaît pas dans les schémas persistés.

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| Moteur | SQLite (WAL) |
| Migrations | table `schema_migrations` + scripts ordonnés |
| Résultats lourds | Parquet (via pyarrow) ou JSON compressé |
| Format portable | zip + manifeste + SHA-256 |
| Chiffrement | optionnel, décision documentée ; pas de secrets de toute façon |
| Accès | repositories Python côté sidecar ; l'UI passe par IPC |

## 7. Arborescence concernée

```
packages/agent-core/          # ou packages/storage/ si extrait
├── storage/
│   ├── migrations/
│   ├── repositories.py
│   ├── project_store.py
│   ├── portable.py         # import/export .simproj
│   └── integrity.py
└── tests/
    ├── test_migrations.py
    ├── test_repositories.py
    └── test_simproj.py
```

## 8. Critères d'acceptation

- [ ] Créer, ouvrir, dupliquer, exporter, importer et supprimer un projet fonctionne.
- [ ] Une migration sur une base existante conserve les données.
- [ ] Un `.simproj` exporté puis importé restitue messages, brief, scenarios, runs et permissions.
- [ ] Un `.simproj` corrompu ou d'une version inconnue est refusé avec un message clair.
- [ ] Aucun token/clé API n'est présent dans la base ou l'archive (test automatisé).
- [ ] La fermeture brutale ne corrompt pas la base (WAL + test).
- [ ] Les résultats volumineux ne bloquent pas l'UI.

## 9. Tests et qualité

- Tests de migrations (base vide, base ancienne, base corrompue).
- Tests de repositories (CRUD, transactions, pagination).
- Tests d'aller-retour `.simproj`.
- Test de non-présence de secrets.
- Test de concurrence (deux ouvertures du même projet).
- Test de récupération après arrêt brutal.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Corruption SQLite | WAL, sauvegardes, `integrity_check`, export d'urgence |
| Format `.simproj` instable | `schema_version` + manifeste + tests de compatibilité |
| Fuite de secrets dans l'export | Revue de schéma + test automatisé + export avec liste blanche |
| Projets volumineux | Détail en Parquet, quotas, nettoyage |
| Conflit de versions | Refus explicite et message de mise à jour |

## 11. Estimation

**2 à 3 semaines**.

## 12. Definition of Done

- [ ] Projets persistants et portables validés par tests.
- [ ] Migrations et récupération documentées.
- [ ] ADR stockage et format `.simproj` écrits.
- [ ] Test anti-secrets vert.
- [ ] Import/export utilisables depuis le sidecar.
