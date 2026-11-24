# Checklist de release — See The Future 3.0.0

> **État au 2026-11-24 :** la liste est prête, mais les cases dépendant d'un
> certificat, d'une VM propre ou d'une machine Linux restent ouvertes. Aucune
> release ne doit être publiée avec une case bloquante non cochée.

## 1. Portes automatiques

- [ ] `npm run protocol:check` : schéma et fichiers générés identiques.
- [ ] `npm run typecheck` : aucun diagnostic TypeScript.
- [ ] `npm test` : tests protocole + UI verts.
- [ ] `npm run sidecar:test` et `npm run sidecar:lint`.
- [ ] `npm run storage:test`, `npm run engine:test`, `npm run providers:test`,
      `npm run agent:test`, `npm run benchmarks:test`, `npm run reporting:test`,
      `npm run sandbox:test` (+ leurs lints).
- [ ] `cargo test` puis `cargo clippy --all-targets -- -D warnings`.
- [ ] `npm run ui:check` et `npm run build:web`.
- [ ] `npm run bench` : aucune régression > 20 % sur `docs/perf/baseline.md`.
- [ ] `npm audit --omit=dev` : aucune vulnérabilité critique non traitée.

## 2. Sécurité et secrets

- [ ] `rg -n "sk-|AIza|ghp_|xox[baprs]-"` sur le dépôt et les artefacts : aucun
      secret.
- [ ] Aucune clé, aucun chemin local, aucun nom de projet dans les logs, la
      base, les exports, le cache LLM ni les diagnostics.
- [ ] Le journal local d'erreurs est désactivé par défaut.
- [ ] L'export de diagnostic masque clés, chemins, courriels et noms de projets.
- [ ] Aucun envoi réseau automatique : vérification par capture ou
      configuration sans fournisseur.
- [ ] Les permissions de l'agent, de la sandbox et des fichiers sont revues.

## 3. Packaging et signature

- [ ] Version `3.0.0` alignée dans `package.json`, `tauri.conf.json` et le
      `CHANGELOG.md`.
- [ ] Installateur Windows signé ; signature vérifiée.
- [ ] Installation, lancement, simulation, export et désinstallation sur une VM
      Windows propre.
- [ ] SmartScreen et antivirus (Defender + un moteur en ligne) vérifiés.
- [ ] Build Linux (AppImage/deb) : WebKitGTK, WebGL et repli 2D.
- [ ] Taille de l'installeur consignée ; sidecar empaqueté sans caches.
- [ ] Hash SHA-256 des artefacts publié avec les notes de version.

## 4. Mise à jour

- [ ] Clé de signature de mise à jour conservée hors dépôt.
- [ ] Une mise à jour valide s'installe.
- [ ] Une mise à jour dont la signature est invalide est refusée.
- [ ] Si l'updater automatique n'est pas prêt, la procédure manuelle est
      affichée dans l'application et documentée.

## 5. Parcours utilisateur

- [ ] Un inconnu installe, importe le projet d'exemple, lance un run final,
      ouvre le cockpit et exporte le dossier sans aide.
- [ ] Le parcours guidé peut être ignoré et ne bloque aucune action.
- [ ] Le dossier Markdown et le PDF contiennent les mêmes chiffres que le
      cockpit.
- [ ] Le PDF s'ouvre dans au moins deux lecteurs et contient les accents.
- [ ] Aucun `draft` n'est persisté ni exportable.
- [ ] Un run final sans résultat détaillé ne produit pas de dossier.
- [ ] Hors ligne complet : brief, simulation, résultats, export et explication
      déterministe fonctionnent sans fournisseur.

## 6. Migration et compatibilité

- [ ] Base v2 (projets, runs, benchmarks) migrée vers la version courante sans
      perte.
- [ ] Ouverture, résultats et export après migration.
- [ ] Sauvegarde automatique avant migration destructive vérifiée.
- [ ] `.simproj` round-trip dans la version courante.

## 7. Textes et support

- [ ] Politique de confidentialité et CGU relues (validation juridique).
- [ ] Mentions de transparence visibles dans l'écran « À propos ».
- [ ] `CHANGELOG.md` publié avec limites connues.
- [ ] Canal de support et procédure de rollback annoncés.
- [ ] Guide utilisateur de deux pages maximum.

## 8. Après publication

- [ ] Tag Git annoté et poussé.
- [ ] Artefacts et hash attachés à la release.
- [ ] Notes de version publiées.
- [ ] Veille des premiers retours (crashs, SmartScreen, faux positifs).
