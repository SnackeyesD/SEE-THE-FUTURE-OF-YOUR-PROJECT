# Phase 07 — Sandbox & scripts générés

> **Objectif** : permettre à l'IA d'écrire puis d'exécuter des scripts personnalisés **sans jamais exposer la machine de l'utilisateur**, avec revue humaine et audit.

**Références** : `ARCHITECTURE-DESKTOP.md` §7, §6 (`run_custom_script`), §11.

---

## 1. Contexte et dépendances

- **Dépend de** : phases 05 (outil `run_custom_script`) et 06 (UI de revue).
- **Débloque** : extensions avancées (simulations sur mesure).
- **Principe** : un script généré est du **code non fiable**. Il ne s'exécute jamais sans revue ni sandbox.

## 2. Objectifs

1. Exécution Python isolée via **Pyodide (WebAssembly)** dans un Worker dédié.
2. Isolation identique sur Windows, Linux, macOS, sans droits système.
3. Aucun accès réseau ni fichier hors des données explicitement fournies.
4. Limites de temps et de mémoire.
5. Analyse statique préalable + liste d'imports autorisés.
6. Revue humaine obligatoire avant exécution.
7. Résultats uniquement en données structurées validées.
8. Journal de tout code exécuté.

## 3. Périmètre

**Inclus**
- Worker Pyodide, chargement des paquets numpy/pandas.
- Pont de données (entrée/sortie) typé et borné.
- Analyse statique (AST) et politique d'imports.
- Écran de revue/approbation.
- Timeout, mémoire, annulation.
- Journal d'audit local.
- Tests de sécurité.

**Exclu**
- Scripts shell ou natifs.
- Accès aux clés API ou à la base.
- Exécution automatique sans confirmation (jamais).

## 4. Livrables

- [ ] `packages/sandbox/` complet.
- [ ] Worker Pyodide + gestion du cycle de vie.
- [ ] Analyseur statique et politique d'imports.
- [ ] Contrat d'entrée/sortie (données structurées uniquement).
- [ ] UI de revue du code (affichage, approbation, refus).
- [ ] Journal d'audit consultable.
- [ ] Tests de sécurité et de limites.
- [ ] ADR isolation et politique d'exécution.

## 5. Tâches détaillées

### Lot A — Isolation
- [ ] Charger Pyodide dans un Web Worker (pas dans le thread UI).
- [ ] Isoler le worker de la webview (pas d'accès direct au DOM, au shell ou au sidecar).
- [ ] Vérifier l'absence d'accès réseau (`fetch`, sockets) et fichiers.
- [ ] Politique de redémarrage du worker après exécution (état propre).
- [ ] Documenter pourquoi Pyodide vs sous-processus restreint.

### Lot B — Limites
- [ ] Timeout dur (ex. 10 s) avec interruption.
- [ ] Plafond mémoire (ex. 256 Mo) et comportement en cas de dépassement.
- [ ] Taille maximale du code, des entrées et des sorties.
- [ ] Annulation utilisateur.
- [ ] Tests de scripts qui bouclent ou consomment trop.

### Lot C — Analyse statique
- [ ] Parser Python (AST) côté worker/sidecar.
- [ ] Liste d'imports autorisés (`numpy`, `pandas`, `math`, `statistics`, stdlib sûre).
- [ ] Interdictions : `eval`, `exec`, `compile`, `__import__`, accès `os`/`sys`/`subprocess`/`socket`/`ctypes`, réflexion dangereuse.
- [ ] Refus explicite avec raison lisible.
- [ ] Tests avec scripts malveillants connus.

### Lot D — Contrat de données
- [ ] Entrées : uniquement des données fournies (scénarios, résultats, tables).
- [ ] Sorties : JSON structuré validé par schéma (tables, séries, métriques).
- [ ] Interdire le HTML et tout contenu affiché sans validation.
- [ ] Taille bornée et troncature explicite.
- [ ] Aucun accès aux secrets, à la base ou au système de fichiers.

### Lot E — Revue humaine et UX
- [ ] Afficher le code avec coloration syntaxique.
- [ ] Expliquer ce que fait le script en langage clair (résumé du LLM, marqué comme non fiable).
- [ ] Boutons Approuver / Modifier / Refuser.
- [ ] Avertir si le script dépasse les imports autorisés.
- [ ] Permission `run_custom_script` toujours en « demander ».
- [ ] Ne jamais réutiliser une approbation pour un code différent.

### Lot F — Journal et audit
- [ ] Enregistrer : date, code, hash, résultat, durée, décision utilisateur.
- [ ] Stockage local, exportable.
- [ ] Aucune donnée sensible dans le journal.
- [ ] Consultation depuis les réglages.

### Lot G — Tests
- [ ] Scripts malveillants : accès fichier, réseau, secrets, évasion.
- [ ] Scripts invalides et scripts trop lourds.
- [ ] Script valide numpy/pandas.
- [ ] Vérifier qu'aucun accès réseau/fichier n'est possible.
- [ ] Test de non-fuite de secrets.
- [ ] Test de performance (temps de démarrage du worker).

## 6. Décisions techniques

| Sujet | Choix recommandé |
|---|---|
| Isolation | **Pyodide dans un Web Worker** |
| Alternative | sous-processus Python restreint (moins isolé, à éviter) |
| Paquets | numpy + pandas dans la sandbox uniquement |
| Entrée/sortie | JSON structuré validé |
| Approbation | humaine, obligatoire, non mémorisable pour un autre code |

## 7. Arborescence concernée

```
packages/sandbox/
├── sandbox/
│   ├── worker.js
│   ├── pyodide_runner.py
│   ├── static_analysis.py
│   ├── contract.py
│   ├── limits.py
│   └── audit.py
└── tests/
    ├── malicious/
    ├── valid/
    └── test_limits.py
```

## 8. Critères d'acceptation

- [ ] Un script valide (numpy/pandas) s'exécute et renvoie des données structurées.
- [ ] Toute tentative d'accès réseau, fichier, secret ou système est bloquée.
- [ ] Un script qui boucle est interrompu au timeout.
- [ ] Un dépassement mémoire est contenu sans tuer l'app.
- [ ] Aucun script ne s'exécute sans approbation humaine explicite.
- [ ] Le journal contient le hash et le résultat de chaque exécution.
- [ ] Un script refusé par l'analyse statique ne peut pas être exécuté par contournement.

## 9. Tests et qualité

- Tests de sécurité (scripts malveillants répertoriés).
- Tests de limites (temps, mémoire, taille).
- Tests du contrat de sortie.
- Tests de persistance d'approbation (hash).
- Test d'isolation (pas de pont vers le shell).
- Tests de non-régression après montée de version Pyodide.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Évasion de sandbox | Pyodide + tests adversariaux + pas de pont privilégié |
| Lenteur de démarrage | Préchargement du worker, cache des paquets |
| Incompatibilité de paquets | Versions figées, tests de compatibilité |
| Script utile mais bloqué | Liste d'imports claire, message explicite, mode revue |
| Faux sentiment de sécurité | Documentation des limites, pas d'accès système |

## 11. Estimation

**2 à 3 semaines**.

## 12. Definition of Done

- [ ] Sandbox isolée et testée contre des scripts hostiles.
- [ ] Revue humaine obligatoire dans l'UI.
- [ ] Journal d'audit opérationnel.
- [ ] Aucune fuite de secret démontrée.
- [ ] ADR isolation écrit.
