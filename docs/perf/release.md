# Mesures de release — See The Future 3.0.0

> **État (2026-11-24)** : ce document fixe la procédure et les budgets, mais la
> mesure de release **n'a pas encore été rejouée** sur la machine de référence
> modeste. `docs/perf/latest.json` date de la phase 06 (2026-11-15, moteur
> `0.3.0`, protocole `1.8.0`) et **ne doit pas** servir de preuve pour la
> release. Une régression > 20 % sur un budget bloque la publication.

## 1. Conditions de mesure

Reprendre [`machine-reference.md`](machine-reference.md) :

1. machine modeste de référence : 2 cœurs / 4 threads, ~2,4 GHz, 8 Go de RAM,
   pas de GPU dédié ;
2. arbre propre sur le commit à publier ;
3. applications lourdes fermées, secteur branché, mode performance ;
4. première exécution de `npm run bench` ignorée (imports à froid) ;
5. consigner la **seconde** exécution ;
6. archiver `docs/perf/latest.json`, `latest.md` et le commit mesuré.

Commandes :

```powershell
npm run bench           # orchestrateur : moteur + sidecar + UI
npm run bench:engine
npm run bench:sidecar
npm run bench:ui
```

## 2. Budgets opposables

| Mesure | Cible | Plafond bloquant |
|---|---|---|
| `draft` 500 runs × 36 mois | ≤ 50 ms | 150 ms |
| `final` 5 000 runs × 36 mois | ≤ 400 ms | 1,5 s |
| Annulation | ≤ 100 ms | 250 ms |
| Surface 15×15 × 200 runs | ≤ 8 s | 20 s |
| Mise à jour graphique | ≤ 16 ms | 33 ms |
| Mémoire sidecar | ≤ 500 Mo | 800 Mo |
| Démarrage application | à consigner | — |
| Glissement de curseur | 30–60 i/s réels | aucune interpolation |

Règles :

- une mesure manquante n'est pas un succès : elle est « non disponible » ;
- aucun chiffre d'interface n'est interpolé pour simuler une fluidité ;
- toute dérogation est écrite dans ce fichier avec sa justification et sa date.

## 3. Ce qu'il faut relever en plus des bancs

| Élément | Où | Attendu |
|---|---|---|
| Démarrage à froid (process → `health`) | `latest.md` | < 3 s |
| Démarrage applicatif complet | mesure manuelle, VM propre | < 10 s |
| Premier résultat d'un inconnu | test utilisateur | < 2 min |
| Taille de l'installeur | artefact signé | consignée et comparée |
| Chunk 3D gzip | `npm run build:web` / `bundle:check` | < 1,2 Mo |
| Mémoire sidecar après 20 runs | observation | ≤ 500 Mo |
| Freeze > 200 ms | parcours cockpit | aucun |

## 4. Porte de publication

La release est bloquée si :

- un budget est dépassé de plus de 20 % sans dérogation écrite ;
- `docs/perf/latest.json` ne correspond pas au commit publié ;
- les tests E2E ou de migration ne sont pas verts ;
- un secret ou un chemin local apparaît dans un artefact.

## 5. Historique

| Date | Commit | Moteur | Protocole | Résultat |
|---|---|---|---|---|
| 2026-11-14 | `1b09972` | 0.1.0 | 1.7.0 | baseline phase 01 |
| 2026-11-15 | `bfbbb3e` | 0.3.0 | 1.8.0 | contrôle phase 06 |
| à faire | — | courant | `1.16.0` | **mesure de release 3.0.0 en attente** |
