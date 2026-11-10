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

- [x] `packages/sandbox/` complet.
- [x] Worker Pyodide + gestion du cycle de vie.
- [x] Analyseur statique et politique d'imports.
- [x] Contrat d'entrée/sortie (données structurées uniquement).
- [x] UI de revue du code (affichage, approbation, refus).
- [x] Journal d'audit consultable.
- [x] Tests de sécurité et de limites.
- [x] ADR isolation et politique d'exécution.

## 5. Tâches détaillées

### Lot A — Isolation
- [x] Charger Pyodide dans un Web Worker (pas dans le thread UI).
- [x] Isoler le worker de la webview (pas d'accès direct au DOM, au shell ou au sidecar).
- [x] Vérifier l'absence d'accès réseau (`fetch`, sockets) et fichiers.
- [x] Politique de redémarrage du worker après exécution (état propre).
- [x] Documenter pourquoi Pyodide vs sous-processus restreint.

### Lot B — Limites
- [x] Timeout dur (ex. 10 s) avec interruption.
- [ ] Plafond mémoire (ex. 256 Mo) et comportement en cas de dépassement.
- [x] Taille maximale du code, des entrées et des sorties.
- [x] Annulation utilisateur.
- [x] Tests de scripts qui bouclent ou consomment trop.

### Lot C — Analyse statique
- [x] Parser Python (AST) côté worker/sidecar.
- [x] Liste d'imports autorisés (`numpy`, `pandas`, `math`, `statistics`, stdlib sûre).
- [x] Interdictions : `eval`, `exec`, `compile`, `__import__`, accès `os`/`sys`/`subprocess`/`socket`/`ctypes`, réflexion dangereuse.
- [x] Refus explicite avec raison lisible.
- [x] Tests avec scripts malveillants connus.

### Lot D — Contrat de données
- [x] Entrées : uniquement des données fournies (scénarios, résultats, tables).
- [x] Sorties : JSON structuré validé par schéma (tables, séries, métriques).
- [x] Interdire le HTML et tout contenu affiché sans validation.
- [x] Taille bornée et troncature explicite.
- [x] Aucun accès aux secrets, à la base ou au système de fichiers.

### Lot E — Revue humaine et UX
- [x] Afficher le code avec coloration syntaxique.
- [x] Expliquer ce que fait le script en langage clair (résumé du LLM, marqué comme non fiable).
- [x] Boutons Approuver / Modifier / Refuser.
- [x] Avertir si le script dépasse les imports autorisés.
- [x] Permission `run_custom_script` toujours en « demander ».
- [x] Ne jamais réutiliser une approbation pour un code différent.

### Lot F — Journal et audit
- [x] Enregistrer : date, code, hash, résultat, durée, décision utilisateur.
- [x] Stockage local, exportable.
- [x] Aucune donnée sensible dans le journal.
- [x] Consultation depuis les réglages.

### Lot G — Tests
- [x] Scripts malveillants : accès fichier, réseau, secrets, évasion.
- [x] Scripts invalides et scripts trop lourds.
- [x] Script valide numpy/pandas.
- [x] Vérifier qu'aucun accès réseau/fichier n'est possible.
- [x] Test de non-fuite de secrets.
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
├── see_sandbox/
│   ├── __init__.py
│   ├── limits.py
│   ├── audit.py
│   ├── static_analysis.py
│   └── contract.py
├── src/
│   ├── index.ts
│   └── worker.ts
└── tests/
    ├── malicious/
    ├── valid/
    ├── test_limits.py
    ├── test_fixtures.py
    └── test_static_analysis.py
```

Le runtime Pyodide (moteur, stdlib, `numpy`, `pandas`) est copié dans `apps/desktop/public/pyodide/` par `npm run sandbox:sync` ; ces assets sont ignorés par Git.

## 8. Critères d'acceptation

- [x] Un script valide (numpy/pandas) s'exécute et renvoie des données structurées.
- [x] Toute tentative d'accès réseau, fichier, secret ou système est bloquée.
- [x] Un script qui boucle est interrompu au timeout.
- [ ] Un dépassement mémoire est contenu sans tuer l'app.
- [x] Aucun script ne s'exécute sans approbation humaine explicite.
- [x] Le journal contient le hash et le résultat de chaque exécution.
- [x] Un script refusé par l'analyse statique ne peut pas être exécuté par contournement.

> Mémoire : Pyodide n'expose pas de plafond dur portable. Le worker est isolé et terminé au timeout ou à l'annulation ; la limite de 256 Mo est best effort. Le test de performance du démarrage reste manuel.

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

- [x] Sandbox isolée et testée contre des scripts hostiles.
- [x] Revue humaine obligatoire dans l'UI.
- [x] Journal d'audit opérationnel.
- [x] Aucune fuite de secret démontrée.
- [x] ADR isolation écrit.
