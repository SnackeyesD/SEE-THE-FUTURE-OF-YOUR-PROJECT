# Phase 08 — Benchmarks & données de référence

> **Objectif** : fournir des référentiels locaux (marges, paniers moyens, saisonnalité, coûts) **sourcés, datés, fiables et signés** — le vrai avantage différenciant du produit.

**Références** : `ARCHITECTURE-DESKTOP.md` §9, §1, §6 (`get_benchmark`), §14 (étape 3).

---

## 1. Contexte et dépendances

- **Dépend de** : phases 02 (injection dans le moteur) et 03 (stockage).
- **Débloque** : phases 05 (outil `get_benchmark`), 06 (affichage), 09 (rapport).
- **Attention** : c'est un travail **data et métier**, pas seulement du code. À démarrer tôt.

## 2. Objectifs

1. Définir un schéma de benchmark avec **provenance** complète.
2. Construire un pack par défaut embarqué à l'installation.
3. Signer et vérifier les packs (Ed25519/minisign).
4. Fournir une API de recherche (`get_benchmark`) déterministe.
5. Afficher source, date, fiabilité, pays/secteur dans l'UI.
6. Gérer la fraîcheur, les conflits et les mises à jour.
7. Mettre en place une gouvernance de validation des données.

## 3. Périmètre

**Inclus**
- Schéma JSON des packs et versionnage.
- Outil de construction et de signature (CI).
- Pack par défaut (pays/secteurs prioritaires).
- API de lookup et résolution de conflits.
- Indicateurs de fraîcheur.
- UI de provenance.
- Processus de mise à jour (fichier local ou cloud en phase 10).

**Exclu**
- Toilettage massif de données non validées.
- Scraping sauvage de sources non licites.
- Sync cloud (phase 10).

## 4. Livrables

- [ ] Schéma `benchmark-pack` documenté et versionné.
- [ ] `data/benchmark-packs/` avec au moins un pack par défaut.
- [ ] `pack-builder` + signature + vérification.
- [ ] API `get_benchmark` (filtres : pays, secteur, indicateur, date).
- [ ] Écran/panneau de provenance.
- [ ] Processus de validation et de revue (checklist).
- [ ] Tests de schéma, de signature, de fraîcheur et de conflits.
- [ ] ADR sur la gouvernance des données.

## 5. Tâches détaillées

### Lot A — Schéma
- [ ] Chaque valeur porte : `indicator`, `value`, `unit`, `currency`, `country`, `sector`, `source`, `source_url`, `date`, `reliability`, `notes`.
- [ ] `reliability` : échelle explicite (ex. officielle / étude / estimation).
- [ ] `schema_version` et compatibilité.
- [ ] Validation JSON Schema + Pydantic.
- [ ] Interdiction des valeurs sans source ou sans date.

### Lot B — Pack par défaut
- [ ] Définir le périmètre minimal : marges retail, panier moyen, saisonnalité, coûts locaux, taxes.
- [ ] Collecter et documenter les sources (publiques, licites, citables).
- [ ] Faire relire par une personne du domaine.
- [ ] Embarquer le pack dans l'installateur.
- [ ] Afficher clairement qu'il s'agit d'ordres de grandeur, pas de certitudes.

### Lot C — Signature et intégrité
- [ ] Générer une paire de clés ; clé publique embarquée dans l'app.
- [ ] Signer chaque pack (Ed25519 ou minisign).
- [ ] Vérifier la signature au chargement ; refuser un pack non signé ou altéré.
- [ ] Versionner les clés et prévoir la rotation.
- [ ] Tests de signature valide/invalide/altérée.

### Lot D — Lookup et résolution
- [ ] API : `get_benchmark(indicator, country, sector, date_range)`.
- [ ] Ordre de priorité : pack le plus récent > fiabilité > spécificité géographique.
- [ ] Résolution de conflits documentée et déterministe.
- [ ] Indicateur de fraîcheur (`fresh`, `aging`, `stale`).
- [ ] Fallback explicite (ex. pays proche) avec mention.
- [ ] Intégration au moteur : les hypothèses peuvent référencer un benchmark.

### Lot E — UI
- [ ] Afficher la valeur, l'intervalle, la source, la date et la fiabilité.
- [ ] Lien vers la source.
- [ ] Avertir quand une valeur est ancienne ou estimée.
- [ ] Permettre de remplacer une valeur de benchmark par une saisie utilisateur (tracée).

### Lot F — Mises à jour
- [ ] Format de pack téléchargeable et vérifiable.
- [ ] Mise à jour manuelle (fichier) puis automatique (phase 10).
- [ ] Ne jamais bloquer l'app si la mise à jour échoue.
- [ ] Journal des versions installées.

### Lot G — Gouvernance
- [ ] Checklist de validation (source, date, cohérence, licence).
- [ ] Revue à deux personnes pour les valeurs sensibles.
- [ ] Documentation des limites et des biais.
- [ ] Politique de correction/retrait d'une valeur erronée.

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| Format | JSON versionné, un fichier par pack |
| Signature | Ed25519 (ou minisign) |
| Stockage | embarqué + copie locale versionnée |
| Lookup | déterministe, priorité documentée |
| Fraîcheur | seuils explicites (ex. > 3 ans = stale) |

## 7. Arborescence concernée

```
data/benchmark-packs/
├── schema/
│   └── benchmark-pack.schema.json
├── packs/
│   └── cg-retail-2026.1.json
├── keys/
│   └── public.key
└── tools/
    ├── build_pack.py
    ├── sign_pack.py
    └── verify_pack.py
packages/agent-core/agent_core/tools/benchmarks.py
```

## 8. Critères d'acceptation

- [ ] `get_benchmark` renvoie une valeur avec source, date, fiabilité et pays/secteur.
- [ ] Un pack altéré ou non signé est refusé.
- [ ] Les valeurs obsolètes sont signalées (`stale`).
- [ ] Les conflits sont résolus de façon déterministe et documentée.
- [ ] L'UI affiche toujours la provenance.
- [ ] Le pack par défaut est validé par une relecture métier.
- [ ] L'app fonctionne sans mise à jour réseau.

## 9. Tests et qualité

- Tests de schéma (valeurs manquantes, types, unités).
- Tests de signature (valide, invalide, clé inconnue).
- Tests de lookup (priorité, conflits, fallback).
- Tests de fraîcheur.
- Tests d'intégration avec le moteur (hypothèse liée à un benchmark).
- Revue de données (échantillonnage manuel).

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Données fausses ou biaisées | Sourcing, revue à deux, affichage de la fiabilité |
| Problème de licence | Vérifier les droits, citer les sources, exclure le non-licite |
| Valeurs obsolètes | Indicateur de fraîcheur + mises à jour |
| Fausse autorité | Vocabulaire prudent, intervalles, avertissements |
| Conflits de valeurs | Priorité documentée + fallback explicite |

## 11. Estimation

**3 à 4 semaines** (fortement dépendant du travail de collecte et de validation).

## 12. Definition of Done

- [ ] Pack par défaut signé et embarqué.
- [ ] Lookup et provenance opérationnels.
- [ ] Tests de signature et de conflits verts.
- [ ] Processus de validation documenté.
- [ ] ADR gouvernance des données écrit.
