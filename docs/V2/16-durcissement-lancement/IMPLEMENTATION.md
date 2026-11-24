# Phase 16 — note d'implémentation

- **Date** : 2026-11-24
- **Protocole** : `1.16.0`
- **ADR** : [0019](../../adr/0019-export-pdf-local-et-diagnostic.md)

## Livré

### Export PDF local

- `packages/reporting/see_reporting/pdf.py` : générateur PDF 1.4 minimal
  (Helvetica, WinAnsi), pagination, tableaux, en-têtes répétés, pied de page
  avec avertissement et numéro de page.
- Le PDF est le rendu du **même Markdown** : `build_pdf(report)` appelle
  `build_markdown(report)`, puis met en page. Aucun agrégat n'est recalculé.
- `report.buildPdf` renvoie `contentBase64` et `byteLength` ; le sidecar reste
  seul producteur des octets. Protocole `1.16.0`.
- Bouton « Exporter en PDF » dans `ResultsScreen`, téléchargement binaire local
  via `downloadBase64`.
- Tests : déterminisme, structure PDF, accents, absence de chemins et de
  secrets, refus d'un run absent, nom de fichier `.pdf`.

### Diagnostic et journal local

- `lib/diagnostic.ts` : diagnostic JSON borné (versions, sidecar, 50 derniers
  événements, 10 erreurs), nettoyage des clés, jetons, chemins, courriels et
  noms de projets.
- `lib/crashlog.ts` : journal local `opt-in`, désactivé par défaut, limité à
  10 entrées de 500 caractères, effacé à la désactivation. Aucun envoi réseau.
- Bouton « Exporter le diagnostic » et case « Journal local des erreurs » dans
  l'écran Réglages.
- Tests : masquage, borne, activation/désactivation, stockage corrompu.

### Textes légaux, transparence et « À propos »

- `docs/legal/POLITIQUE-CONFIDENTIALITE.md` : données locales, fournisseur IA
  facultatif, télémétrie absente, rétention, droits.
- `docs/legal/CGU.md` : absence de garantie de prévision, usage, clés, données,
  mises à jour, responsabilité.
- Carte « À propos » : version applicative, protocole, sidecar, licence MIT,
  mention de transparence et résumé dépliable de confidentialité/CGU.
- `CHANGELOG.md`, `docs/release/checklist.md` et `docs/perf/release.md` :
  procédure, budgets opposables et porte de publication. La mesure de release
  sur la machine modeste reste à rejouer.
- `docs/guide-utilisateur.md` (deux pages) et guide rapide dépliable dans
  l'écran « À propos ».

### Documentation

- ADR 0019 : PDF local, diagnostic sans télémétrie, textes provisoires.
- Phase 15 mise à jour : le PDF n'est plus reporté.
- Tableau V3 et plan maître : protocole `1.16.0`, phase 16 démarrée.

### Dépendances de test

- `vitest` passe de `3.2.7` à `5.1.1` et `vite` de `6.0.3` à `6.4.6` pour
  corriger les avis `tinypool` (critique) et `@vitest/mocker` (modéré).
  `npm audit` ne remonte plus aucune vulnérabilité.
- Prérequis : Node `^22.12`, `^24` ou `>=26` pour Vitest 5.
- La suite UI reste verte sans modification des tests existants.

### Détection de secrets

- `npm run secrets:check` parcourt uniquement les fichiers **suivis par Git**
  (`git ls-files`) : un `.env` local ou une base ne peut donc pas fuiter dans
  la sortie. Les tests et fixtures sont exclus car ils contiennent de fausses
  clés destinées à vérifier le masquage.
- Motifs : clés OpenAI/Google/GitHub/Slack, clés privées PEM, affectations
  `api_key`/`client_secret`. La sortie indique le fichier et le motif, jamais
  la valeur.
- Exécuté dans le job `web` de la CI. Un test manuel avec une fausse clé a
  confirmé le code de sortie `1` et le masquage.

## Écarts assumés

- **Version non bumpée.** `package.json`, `tauri.conf.json` et `Cargo.toml`
  restent en `0.1.0` : le passage à `3.0.0` accompagne la release signée, pas
  une build de développement. L'écran « À propos » affiche donc la version
  réellement compilée.
- **Signature et packaging non réalisés.** Ils exigent le certificat Windows
  (démarré en phase 01), une VM propre et une machine Linux. Le code et la
  checklist sont prêts ; aucune release ne doit être publiée sans ces cases.
- **Mises à jour signées non configurées.** La procédure manuelle et la
  vérification de signature restent à brancher sur les artefacts réels.
- **Tests E2E Playwright non ajoutés.** La phase les autorise explicitement
  pour la première fois ; le harnais existant (Vitest + Testing Library) couvre
  les parcours critiques. L'ajout de Playwright demande un shim IPC déterministe
  et une décision d'outillage qui n'a pas été prise dans cette session.
- **Migration v2 → v3 réelle non rejouée.** Un test automatisé couvre désormais
  la migration d'une base v5 (projets, scénarios, runs) vers le schéma courant,
  puis l'export et le ré-import `.simproj`. Le scénario « copie d'une base v2
  réelle » reste à exécuter sur une machine de test.
- **Boîte de dialogue native d'enregistrement** toujours différée : le
  téléchargement webview fonctionne et ne change ni le contenu ni le
  déterminisme.
- **Test utilisateur final non réalisé.** Le parcours d'exemple est automatisé,
  mais la mesure « premier résultat en moins de deux minutes » avec un inconnu
  reste ouverte.
- **Pack `2026.2` non signé.** L'exemple continue d'épingler `2026.1`.

## Vérifications exécutées

```powershell
npm run protocol:generate
npm run protocol:check
npm run typecheck
npm test                 # protocole + 276 tests UI
npm run sidecar:test
npm run sidecar:lint
npm run reporting:test
npm run reporting:lint
cargo check
cargo clippy --all-targets
```

Résultats consignés dans le compte rendu de session. `cargo test` reste bloqué
au démarrage du binaire de test Windows (`STATUS_ENTRYPOINT_NOT_FOUND`),
indépendamment de ce lot : `cargo check` et `cargo clippy` passent.
