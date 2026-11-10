# ADR 0008 — Isolation et politique d'exécution des scripts générés

- Statut : accepté
- Date : 2026-11-10
- Contexte : phase 07, outil agent `run_custom_script`

## Décision

Les scripts Python proposés par le LLM ne sont jamais exécutés par le sidecar, le shell Rust ou la base. Ils s'exécutent uniquement dans un Web Worker du frontend, via Pyodide (WebAssembly), après analyse statique et approbation humaine explicite.

### Analyse statique

- Analyse AST côté package Python `see_sandbox`, exposée par les méthodes sidecar `sandbox.analyze` et `sandbox.audit.record`.
- Liste d'imports autorisés : `collections`, `datetime`, `decimal`, `fractions`, `functools`, `itertools`, `json`, `math`, `numpy`, `pandas`, `random`, `statistics`.
- Refus des modules système et réseau (`os`, `sys`, `subprocess`, `socket`, `ctypes`, `pathlib`, `shutil`, `importlib`, `http`, `urllib`, `requests`, `ssl`, `pickle`, etc.).
- Refus des appels et attributs dangereux (`eval`, `exec`, `compile`, `open`, `__import__`, accès aux attributs privés et aux noms dunder).
- Le hash SHA-256 du code est calculé par le sidecar ; le navigateur le recalcule et le vérifie avant exécution.

### Exécution

- Un Web Worker est créé pour chaque exécution, puis terminé après succès, erreur, timeout ou annulation. Aucun état Python n'est réutilisé.
- Pyodide, `numpy` et `pandas` sont servis depuis les assets locaux de l'application (`/pyodide/`). Aucun CDN n'est requis à l'exécution.
- Le worker est un module worker. Le runtime Pyodide et son module WebAssembly sont chargés localement ; `fetch`, `WebSocket`, `XMLHttpRequest` et `EventSource` sont neutralisés après le chargement des paquets.
- La CSP Tauri autorise les scripts et workers de même origine, la compilation WebAssembly (`wasm-unsafe-eval`) et les requêtes `connect-src 'self'` nécessaires au chargement local de Pyodide.
- Un garde d'import Python bloque les ponts dangereux (`js`, `pyodide`, `_pyodide`, `micropip`, `pyodide_js`) même si l'analyse statique était contournée.
- Le script doit définir `main(data)` et retourner uniquement un objet structuré (`summary`, `metrics`, `series`, `tables`). Le JSON est validé par schéma côté Python et côté TypeScript, sans HTML.
- Limites : code 32 Kio, entrée/sortie 256 Kio, logs 8 Kio, 10 s d'exécution, 60 s de démarrage, 256 Mio de mémoire best effort.
- La mémoire n'a pas de plafond dur portable dans Pyodide. L'isolation du worker et sa terminaison contiennent l'impact sans tuer l'application ; cette limite est documentée dans l'UI.

### Revue humaine et audit

- L'outil `run_custom_script` demande toujours une permission, puis renvoie une proposition avec code, hash, analyse et explication marquée comme non fiable.
- L'approbation porte sur le hash affiché. Toute modification du code relance l'analyse et invalide l'approbation.
- Chaque décision et exécution est enregistrée dans `sandbox_audit` : date, code, hash, décision, statut, résultat validé, durée et erreur éventuelle.
- L'audit est exportable dans `results/<projet>/sandbox-audit.json`. Aucune clé API, secret ou chemin sensible n'y est stocké.

### Conséquences

- La sandbox est disponible sur Windows, Linux et macOS sans droits système et sans processus natif.
- Le démarrage du worker reste plus lent qu'un processus préchauffé ; un worker par exécution privilégie l'état propre.
- La politique doit être testée à chaque montée de version de Pyodide ; les versions et les empreintes des assets sont figées.
- Une faille dans WebAssembly, le navigateur ou Pyodide reste hors du modèle de menace applicatif ; la sandbox réduit la surface sans remplacer les mises à jour de sécurité.

## Alternatives écartées

- **Sous-processus Python restreint** : dépendant de l'OS, plus difficile à isoler et à limiter sans conteneur.
- **Exécution dans le sidecar** : accès direct aux fichiers, à la base et aux secrets, donc refusée.
- **Exécution automatique après analyse** : contraire à l'exigence de revue humaine obligatoire.
