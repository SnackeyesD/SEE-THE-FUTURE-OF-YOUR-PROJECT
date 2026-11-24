# Phase 16 — Durcissement & lancement

> **Objectif** : transformer un build de développement en produit installable, signé, testé sur machine modeste, utilisable hors ligne, avec des textes légaux et une procédure de release reproductible.

**Références** : `V3-COCKPIT.md` §10 (D3–D5), §14, §15 ; plan maître §11.
**Dépend de** : toutes les phases retenues.
**Débloque** : le lancement.
**Profil** : senior infra/release + tous ; 8–10 jours.
**Jalon D** : produit installable, signé, utilisable par un inconnu sans aide.

> **État (2026-11-24)** : première tranche livrée — PDF local, diagnostic
> nettoyé, journal d'erreurs opt-in, textes légaux provisoires, écran
> « À propos », `CHANGELOG.md` et checklist de release. Voir
> [`IMPLEMENTATION.md`](IMPLEMENTATION.md) pour les écarts (signature, VM,
> Linux, E2E, migration réelle).

---

## 1. Contexte

À ce stade, le cockpit fonctionne en développement. Il reste les sujets qui bloquent une mise entre les mains d'un utilisateur :

- signature Windows et SmartScreen ;
- mises à jour signées ;
- rapports de crash opt-in ;
- politique de confidentialité, CGU, mentions de transparence ;
- tests E2E, migration depuis la v2, machine modeste, hors ligne ;
- vérification des budgets et des secrets.

## 2. Périmètre

**Inclus**

- Installateur Windows signé, installateur Linux.
- Mises à jour signées (Tauri updater) ou procédure manuelle documentée.
- Télémétrie/crash opt-in, sans contenu de projet.
- Textes légaux et écran « À propos ».
- Tests E2E des parcours critiques.
- Tests de migration, de machine modeste, de VM propre, hors ligne.
- Portes de performance et de sécurité.
- Checklist de release et version `3.0.0`.

**Exclu**

- Cloud, comptes, synchronisation.
- Nouveaux modèles.

## 3. Livrables

- [ ] Installateur Windows signé + vérification SmartScreen.
- [ ] Build Linux (AppImage/deb) testé.
- [ ] Configuration de mise à jour signée (ou procédure manuelle).
- [x] Rapports de crash opt-in (si activés) avec scrubbing. *Journal local sans envoi, désactivé par défaut.*
- [x] Politique de confidentialité, CGU, mentions de transparence. *Provisoires, dans `docs/legal` et l'écran « À propos ».*
- [ ] Suite E2E Playwright en mode web + shim IPC.
- [ ] Tests de migration v2 → v3 sur base réelle. *Migration v5 → courant et round-trip `.simproj` couverts automatiquement ; copie d'une base v2 réelle à exécuter.*
- [x] `docs/perf/release.md` et `docs/release/checklist.md`. *Procédure livrée ; mesure de release sur machine modeste en attente.*
- [ ] `CHANGELOG.md` et version `3.0.0`. *`CHANGELOG.md` livré ; bump de version à faire avec la release.*

## 4. Tâches détaillées

### Lot A — Signature et packaging

- [ ] Finaliser le certificat Windows (démarré en phase 01) ; signer l'exécutable et l'installateur.
- [ ] Vérifier sur une **VM Windows propre** : installation, lancement, SmartScreen, désinstallation.
- [ ] Vérifier les faux positifs antivirus (au moins Defender + un moteur en ligne).
- [ ] Build Linux : vérifier WebKitGTK, WebGL/repli, tray, raccourcis.
- [ ] Réduire la taille de l'installeur : sidecar Nuitka/PyInstaller, exclure les caches, vérifier les licences.
- [ ] Version `3.0.0`, numéro de build, hash publié.

### Lot B — Mises à jour

- [ ] Configurer Tauri Updater avec clé de signature ; clé privée hors dépôt.
- [ ] Flux : vérification, téléchargement, vérification de signature, installation, redémarrage.
- [ ] Test : v3.0.0 → v3.0.1 factice sur VM propre.
- [ ] Si l'updater n'est pas prêt : documenter la procédure manuelle et l'afficher.
- [ ] Ne jamais mettre à jour sans signature valide.

### Lot C — Crash et diagnostic

- [x] Rapports de crash **opt-in** : activation explicite, contenu minimal (version, OS, stack), jamais le projet ni les clés. *Journal local : aucun envoi réseau dans cette version.*
- [x] Scrubbing des chemins, noms de projet, clés API, payloads.
- [x] Bouton « exporter un diagnostic » local (logs + version) pour le support.
- [x] Rétention et suppression documentées.
- [x] Si désactivé : aucun envoi réseau.

### Lot D — Légal et transparence

- [x] Politique de confidentialité : données locales, ce qui part vers le fournisseur IA, télémétrie. *Provisoire.*
- [x] CGU : usage, limites, absence de garantie de prévision. *Provisoires.*
- [x] Mentions dans l'app : « simulation basée sur vos hypothèses, pas une prévision garantie », graine, version moteur.
- [x] Écran « À propos » : versions, licences open source, contact. *Contact à publier avec la release.*
- [ ] Vérifier la conformité des packs de benchmarks (sources, licences).

### Lot E — E2E et non-régression

- [ ] Playwright en mode web (`npm run dev:web`) avec shim IPC déterministe (D5 : **introduit ici uniquement**, aucun nouvel outil de test avant cette phase ; taux d'échec < 2 %, aucun test flaky toléré) :
  - parcours : projet → hypothèses → simulation → cockpit ;
  - glissement de curseur → draft/final ;
  - ajout d'événement ;
  - objectif ;
  - export du rapport.
- [ ] Tests Tauri natifs (smoke) sur Windows : lancement, sidecar, simulation.
- [ ] Tests de migration v2 → v3 :
  - base avec projets, runs, benchmarks ;
  - migration 0006 ;
  - ouverture, résultats, export.
- [ ] Test sur machine modeste de référence : démarrage, draft/final, surface, 3D/repli.
- [ ] Test hors ligne complet : aucune requête réseau (fournisseur non configuré).
- [ ] Vérifier qu'aucun `draft` n'est persisté.
- [ ] Vérifier qu'aucun secret n'apparaît dans les logs, la base, les exports, le cache LLM.

### Lot F — Portes de qualité

- [ ] `npm run typecheck`, `npm run lint`, `npm run test`, `npm run protocol:check`, `npm run ui:check`, `cargo test`, tests Python.
- [ ] `npm run bench` : régression > 20 % bloque la release.
- [ ] `npm audit` / audit Python : aucune vulnérabilité critique non traitée.
- [ ] Revue des permissions : agent, sandbox, provider, fichiers.
- [ ] Vérifier le mode hors ligne et le mode « aucun fournisseur ».

### Lot G — Release

- [ ] `CHANGELOG.md` : nouveautés, corrections, limites connues.
- [ ] Checklist de release signée : version, hash, tests, captures, décisions.
- [ ] Tag Git, artefacts, notes de version.
- [ ] Canal de support et procédure de rollback.
- [ ] Annonce interne et guide utilisateur (2 pages maximum).

## 5. Critères d'acceptation

- [ ] Installation sur VM propre sans admin surprise, lancement < 10 s.
- [ ] Signature valide ; SmartScreen ne bloque pas anormalement.
- [ ] Mise à jour signée testée (ou procédure manuelle claire).
- [ ] Tous les parcours critiques passent en E2E.
- [ ] Migration v2 → v3 sans perte.
- [ ] Fonctionne hors ligne, sans fournisseur.
- [ ] Aucun secret dans les logs/exports/base.
- [ ] Budgets de performance respectés ou dérogation consignée.
- [ ] Textes légaux et de transparence présents.
- [ ] Un inconnu réalise le parcours sans aide (test utilisateur final).

## 6. Tests de release

| Test | Attendu |
|---|---|
| VM Windows propre | Install, lancement, simulation, désinstallation |
| VM Windows sans réseau | Parcours complet hors ligne |
| Machine modeste | Budgets §6 du plan |
| Pop!_OS/Ubuntu | WebKitGTK, WebGL/repli, install |
| Migration base v2 | Aucune perte, runs lisibles |
| Mise à jour signée | Succès ; signature invalide refusée |
| Crash opt-in | Envoi minimal, scrubbing |
| Export `.simproj` | Round-trip v3 |
| Rapport | Chiffres identiques au cockpit |
| Secrets | Grep + inspection logs/base/cache |

## 7. Performance et stabilité

- Démarrage mesuré et consigné.
- Aucun freeze > 200 ms sur les parcours critiques.
- Mémoire sidecar ≤ 500 Mo après 20 runs.
- Aucune fuite de listeners IPC ou de ressources 3D.
- Taux d'échec des E2E < 2 % (tests stables, pas de flaky toléré).

## 8. Risques

| Risque | Mitigation |
|---|---|
| Certificat tardif | Démarré en phase 01, plan B documenté |
| SmartScreen/antivirus | Signature, tests VM propre, soumission |
| Migration destructive | Backup, test sur base réelle, rollback |
| E2E fragiles | Shim déterministe, attentes explicites |
| Télémétrie intrusive | Opt-in, scrubbing, documentation |
| Temps insuffisant | Couper 3D/pitch, jamais les tests ni la signature |

## 9. Definition of Done

- [ ] Installateur signé et testé.
- [ ] Mises à jour signées ou procédure manuelle.
- [ ] Textes légaux et transparence en place.
- [ ] E2E et migration verts.
- [ ] Tests machine modeste et hors ligne consignés.
- [ ] Checklist de release archivée.
- [ ] **Jalon D validé** : un inconnu peut installer, simuler et exporter sans aide.
