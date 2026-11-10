# Phase 10 — Distribution, mises à jour & cloud optionnel

> **Objectif** : rendre le produit installable, signé et maintenable — avec des services cloud **strictement optionnels** qui ne bloquent jamais le cœur local.

**Références** : `ARCHITECTURE-DESKTOP.md` §10, §11, §12, §14 (étapes 4–5).

---

## 1. Contexte et dépendances

- **Dépend de** : toutes les phases précédentes.
- **Débloque** : mise en marché, support, évolutions.
- **Règle d'or** : supprimer le cloud ne doit casser **aucune** fonction de simulation.

## 2. Objectifs

1. Installateurs **signés** Windows (prioritaire), Linux, puis macOS.
2. Mises à jour **signées** avec canaux stable/bêta et rollback.
3. Signature de code (certificat Windows, notarisation macOS) et réduction des alertes SmartScreen.
4. Télémétrie et rapports de crash **opt-in**, sans contenu de projet.
5. Services cloud optionnels : sync chiffrée, distribution des benchmarks, partage de rapports, comptes/abonnement.
6. Observabilité, runbooks, support.
7. Processus de release reproductible.

## 3. Périmètre

**Inclus**
- Packaging et signature des installateurs.
- Updater Tauri signé.
- CI/CD de release, publication GitHub Releases.
- Cloud : API Django réutilisée, PostgreSQL, stockage objet, file de tâches, CDN, supervision.
- Sync E2E, partage, comptes, paiement (si modèle payant).
- Télémétrie opt-in et rapports de crash.
- Documentation d'exploitation.

**Exclu**
- Fonctionnalités produit nouvelles (elles retournent au backlog).
- Refonte de l'architecture locale.

## 4. Livrables

- [ ] Installateurs Windows/Linux/macOS signés.
- [ ] Updater signé + canaux + rollback.
- [ ] Pipeline de release (CI/CD) et notes de version.
- [ ] Service cloud (si GO) : sync, benchmarks, partage, comptes.
- [ ] Télémétrie/crash opt-in.
- [ ] Monitoring (Sentry, métriques) et alertes.
- [ ] Runbooks (incident, rollback, fuite de secret, panne cloud).
- [ ] Politique de confidentialité et mentions légales.
- [ ] ADR distribution, sync et modèle économique.

## 5. Tâches détaillées

### Lot A — Packaging et signature
- [ ] Installateur Windows (MSI/NSIS) signé avec certificat de signature de code.
- [ ] Empaquetage du sidecar par OS/architecture (Nuitka), signature incluse.
- [ ] Linux : AppImage/deb ; macOS : notarisation.
- [ ] Vérification de signature au lancement et à la mise à jour.
- [ ] Test sur VM Windows propre (SmartScreen, antivirus).
- [ ] Documentation des faux positifs et du support.

### Lot B — Mises à jour
- [ ] Updater Tauri avec manifeste signé.
- [ ] Canaux stable / bêta.
- [ ] Téléchargement reprenable, vérification d'intégrité.
- [ ] Rollback et conservation de la version précédente.
- [ ] Migration de schéma de données lors des mises à jour.
- [ ] Message clair si hors ligne.

### Lot C — Release
- [ ] CI/CD : build matrice, tests, signature, publication.
- [ ] Versionnement sémantique + journal des changements.
- [ ] Notes de version générées.
- [ ] Environnements dev/staging/prod (cloud).
- [ ] Builds reproductibles et artéfacts conservés.
- [ ] Procédure de hotfix.

### Lot D — Cloud optionnel
- [ ] Réutiliser l'API Django de la v1 si pertinente ; sinon service minimal.
- [ ] PostgreSQL managé avec sauvegardes, stockage objet (R2/S3), file de tâches, CDN.
- [ ] **Sync** des projets : chiffrement de bout en bout si possible, résolution de conflits documentée, opt-in.
- [ ] Distribution des packs de benchmarks signés + mises à jour.
- [ ] Partage de rapports par lien : expiration, révocation.
- [ ] Comptes et abonnement (si retenu), paiement Mobile Money.
- [ ] Aucun compte requis pour l'usage local.
- [ ] Déconnexion totale : l'app reste pleinement fonctionnelle.

### Lot E — Observabilité et support
- [ ] Télémétrie opt-in (événements anonymes, jamais de contenu de projet).
- [ ] Rapports de crash opt-in.
- [ ] Sentry/metrics/alertes.
- [ ] Tableau de bord de santé du service cloud.
- [ ] Runbooks : incident, rollback, clé compromise, panne fournisseur, panne cloud.
- [ ] Canal de support et procédure de réponse.

### Lot F — Légal et confiance
- [ ] Politique de confidentialité : ce qui est envoyé au fournisseur IA choisi.
- [ ] Mentions légales, licences tierces (numpy, Pyodide, polices).
- [ ] Conditions d'utilisation et politique de remboursement (si payant).
- [ ] Page « vos données » : export/suppression.
- [ ] Vérification des licences des benchmarks.

### Lot G — Tests de bout en bout
- [ ] Installation propre → lancement → parcours complet.
- [ ] Mise à jour depuis N-1 → données préservées.
- [ ] Rollback.
- [ ] Mode hors ligne complet.
- [ ] Cloud indisponible → aucune fonction locale cassée.
- [ ] Scan de sécurité des dépendances et des binaires.

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| Installateurs | Tauri bundler + signature |
| Updater | Tauri updater signé, canaux |
| Cloud | Django + PostgreSQL + R2/S3 + file de tâches |
| Sync | opt-in, chiffrement E2E, conflits documentés |
| Télémétrie | opt-in, sans contenu de projet |
| Paiement | selon modèle, Mobile Money si marché visé |

## 7. Arborescence concernée

```
infra/
├── ci/
├── release/
├── signing/
└── runbooks/
apps/cloud/            # (optionnel)
├── api/
├── sync/
├── benchmarks/
└── billing/
```

## 8. Critères d'acceptation

- [ ] L'installateur Windows est signé et s'installe sans avertissement bloquant sur une VM propre.
- [ ] Une mise à jour signée s'installe et préserve les données ; un rollback est possible.
- [ ] Un binaire non signé/altéré est refusé.
- [ ] L'app complète fonctionne sans compte et sans Internet (avec Ollama).
- [ ] Si le cloud tombe, aucune fonction locale n'est bloquée.
- [ ] La sync est opt-in, chiffrée, et la révocation fonctionne.
- [ ] La télémétrie est désactivée par défaut et sans contenu de projet.
- [ ] Les runbooks existent et sont testés au moins une fois.

## 9. Tests et qualité

- Tests d'installation/mise à jour/rollback sur VM propres.
- Tests de signature (valide, altérée, expirée).
- Tests hors ligne complets.
- Tests de panne cloud.
- Tests de sync (conflits, révocation, gros projets).
- Audit de sécurité des dépendances et des binaires.
- Test de restauration de sauvegarde cloud.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Coût et délai de signature | Lancer la démarche tôt (phase 01) |
| Cloud qui devient obligatoire | Tests hors ligne, architecture optionnelle |
| Fuite de données via sync | Chiffrement E2E, opt-in, audit |
| Coûts d'infra | Dimensionnement, alertes, quotas |
| Incident de mise à jour | Rollback, canaux, tests sur VM |
| Dépendance à un fournisseur | Modèle agnostique, fallback local |

## 11. Estimation

**3 à 5 semaines** (hors délais administratifs de signature et de paiement).

## 12. Definition of Done

- [ ] Produit installable, signé, mis à jour.
- [ ] Cloud optionnel et non bloquant.
- [ ] Télémétrie opt-in et conforme.
- [ ] Runbooks et support en place.
- [ ] ADR distribution, sync et modèle économique écrits.
- [ ] Décision de diffusion (gratuit/licence/abonnement) appliquée.
