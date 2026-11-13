# Phase 09 — Rapports, export & partage

> **Objectif** : transformer un projet en livrable clair (PDF/Markdown), vérifiable et sans secret, exportable hors ligne, partageable en option.

**Références** : `ARCHITECTURE-DESKTOP.md` §6 (`export_report`), §8 (`.simproj`), §10 (partage).

---

## 1. Contexte et dépendances

- **Dépend de** : phases 06 (résultats/UI) et 08 (benchmarks/provenance).
- **Débloque** : phase 10 (partage cloud).
- **Principe** : un rapport doit être compréhensible par un tiers qui n'a pas utilisé l'app.

## 2. Objectifs

1. Générer un rapport **PDF** et **Markdown** fidèle aux résultats.
2. Inclure les graphiques, les hypothèses, les sources et les avertissements.
3. Séparer clairement chiffres du moteur et narration du LLM.
4. Garantir l'absence de secrets et de données personnelles non voulues.
5. Permettre l'export `.simproj` et la réouverture.
6. Préparer le partage par lien (activable phase 10), désactivé hors ligne.
7. Archiver/versionner les rapports générés.

## 3. Périmètre

**Inclus**
- Modèle et mise en page du rapport.
- Rendu PDF (offline) et Markdown.
- Intégration des graphiques et tableaux.
- Outil `export_report`.
- Redaction/vérification anti-secrets.
- Historique des exports.
- Contrat de partage (implémentation cloud en phase 10).

**Exclu**
- Hébergement des liens de partage (phase 10).
- Sync cloud (phase 10).
- Facturation (phase 10).

## 4. Livrables

- [ ] Générateur de rapport (PDF + Markdown).
- [ ] Modèle de document documenté.
- [ ] Outil agent `export_report` relié aux permissions.
- [ ] Vérification anti-secrets avant écriture.
- [ ] Historique des exports.
- [ ] Export `.simproj` exposé dans l'UI.
- [ ] Tests de rendu et de sécurité.
- [ ] ADR format de rapport et partage.

## 5. Tâches détaillées

### Lot A — Modèle de rapport
- [ ] Structure : page de garde, résumé exécutif, idée/brief, hypothèses, méthodologie, résultats, graphiques, sensibilité, limites, sources, annexes.
- [ ] Vocabulaire prudent : intervalles, incertitudes, ordres de grandeur.
- [ ] Distinguer visuellement « calculé par le moteur » et « interprété par l'IA ».
- [ ] Mention de la version du moteur et de la date des benchmarks.
- [ ] Pagination, sommaire, numérotation.

### Lot B — Rendu
- [ ] PDF généré **hors ligne** (bibliothèque Python ou Rust).
- [ ] Markdown propre et lisible.
- [ ] Graphiques exportés en image vectorielle/raster de qualité.
- [ ] Tableaux de sensibilité et de scénarios.
- [ ] Gestion des longues listes et des coupures de page.
- [ ] Polices embarquées (pas de dépendance réseau).

### Lot C — Intégration agent
- [ ] Outil `export_report` : format, portée, langue.
- [ ] Permission par défaut « demander ».
- [ ] Validation des paramètres.
- [ ] Erreurs claires (disque plein, chemin invalide).
- [ ] Ne jamais inclure de clé API, token ou chemin sensible.

### Lot D — Sécurité et redaction
- [ ] Liste blanche des champs exportés.
- [ ] Vérification anti-secrets avant génération (motifs de clés, tokens).
- [ ] Avertir si un contenu utilisateur ressemble à un secret.
- [ ] Test automatisé sur un projet piégé.
- [ ] Métadonnées PDF nettoyées (pas de chemins locaux inutiles).

### Lot E — Export projet et historique
- [ ] Export `.simproj` depuis l'UI (déjà implémenté phase 03).
- [ ] Historique : date, format, taille, hash.
- [ ] Régénération d'un rapport depuis un projet archivé.
- [ ] Ouverture d'un `.simproj` et régénération.

### Lot F — Partage (préparation)
- [ ] Définir le contrat d'un lien de partage (contenu, expiration, révocation).
- [ ] Désactivé et invisible hors ligne.
- [ ] Aucun envoi automatique.
- [ ] Documenter les implications de confidentialité.
- [ ] Implémentation serveur en phase 10.

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| PDF | génération locale, dépendance épinglée, polices embarquées |
| Markdown | texte + images référencées dans l'archive |
| Graphiques | rendu côté UI ou sidecar, images intégrées |
| Sécurité | liste blanche + scan anti-secrets |
| Partage | opt-in, contrat minimal, serveur en phase 10 |

## 7. Arborescence concernée

```
packages/agent-core/agent_core/tools/export.py
packages/report/
├── report/
│   ├── template.py
│   ├── render_pdf.py
│   ├── render_markdown.py
│   ├── assets/
│   └── redaction.py
└── tests/
    ├── test_render.py
    └── test_no_secrets.py
```

## 8. Critères d'acceptation

- [ ] Un PDF complet est généré hors ligne et s'ouvre correctement.
- [ ] Le rapport contient hypothèses, résultats, graphiques, sources et limites.
- [ ] Les chiffres du rapport correspondent exactement au moteur.
- [ ] Aucun secret n'apparaît (test sur projet piégé).
- [ ] Le Markdown est lisible et complet.
- [ ] L'export `.simproj` et la réouverture fonctionnent.
- [ ] Le partage est absent/désactivé hors ligne et explicitement opt-in.

## 9. Tests et qualité

- Tests de rendu (PDF non vide, pages, images).
- Tests de contenu (champs obligatoires présents).
- Tests anti-secrets.
- Tests de fidélité chiffres UI ↔ rapport.
- Tests de gros projets et de caractères spéciaux.
- Test d'accessibilité du PDF (lecture, ordre logique).

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Fuite de secret dans un rapport | Liste blanche + scan + test piégé |
| Rendu PDF cassé selon l'OS | Dépendance figée, tests multi-OS |
| Rapport trompeur | Séparation chiffres/IA, limites, sources, intervalles |
| Poids des images | Compression, résolution adaptée |
| Partage non consenti | Opt-in, confirmation, révocation |

## 11. Estimation

**2 semaines**.

## 12. Definition of Done

- [ ] PDF et Markdown générés hors ligne et testés.
- [ ] Aucun secret dans les exports.
- [ ] Outil `export_report` avec permission.
- [ ] Contrat de partage documenté.
- [ ] ADR écrit.
