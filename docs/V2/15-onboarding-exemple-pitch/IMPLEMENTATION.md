# Phase 15 — note d'implémentation

- **Date** : 2026-11-23
- **Protocole** : `1.15.0`
- **ADR** : [0018](../../adr/0018-projet-exemple-dossier-pitch.md)

## Livré

### Modèle importable

- `data/examples/retail-depot-brazzaville/template.json` : dépôt de revente,
  36 mois, devise `XAF`, graine `42`, trois événements, une branche
  « Prix -10 % ».
- `data/examples/retail-depot-brazzaville/README.md` : sourcing, hypothèses
  estimées et limites.
- `sidecar/template_service.py` : validation complète avant écriture, chemins
  confinés, IDs neufs, compensation par suppression du projet en cas d'échec.
  Le répertoire est résolu par `SEE_EXAMPLES_DIR`, sinon `data/examples` du
  dépôt ; le bundle Tauri embarque `data/examples` sous `examples/`.
- Méthodes `template.list` et `project.createFromTemplate`, commandes Rust
  `template_list` / `project_create_from_template`, fonctions IPC
  `listTemplates` / `createProjectFromTemplate`, carte « Partir d'un projet
  d'exemple » dans `ProjectsScreen`.

Le pack utilisé reste **`cg-brazzaville-retail-2026.1`**. Le brouillon
`2026.2` n'est pas signé sur cette machine : la clé privée est absente. Le
modèle référence donc le pack vérifiable hors ligne, et le sourcing détaillé
reste dans `sourcing-pack-cg.md`.

### Dossier de pitch

- `packages/reporting` : contrat `ReportInput` versionné, formatage français,
  constructeur Markdown déterministe. Aucun agrégat recalculé. Chaque
  hypothèse est formatée avec l'unité déclarée par le moteur (`XAF`,
  `unités/mois`, `%`, `mois`) : le rapport ne devine ni devise ni grandeur. La
  devise affichée est celle du résultat, pas un défaut de projet.
- `sidecar/report_service.py` : sélection d'un run **final**, lecture du
  résultat détaillé, assemblage des branches et versions, appel de
  `build_markdown`.
- Méthode `report.build`, commande Rust `report_build`, fonction IPC
  `buildReport`, bouton « Exporter le dossier » dans `ResultsScreen`.
- Tests : déterminisme, absence de fuite de chemins/clés, refus des runs
  absents, valeurs indisponibles rendues explicitement.

### Parcours guidé

- `components/onboarding/GuidedTour.tsx` : cinq étapes, skippable, `Échap`,
  navigation clavier, mémorisation par projet, réinitialisable en supprimant
  `seefuture.tour.<projectId>`.
- Affiché uniquement lorsque les métadonnées du projet portent
  `templateId = retail-depot-brazzaville`.
- Aucun appel IA, aucun blocage de l'interface.

### Transparence

- Mention « simulation basée sur vos hypothèses, pas une prévision garantie »
  dans le dossier.
- Graine, version du moteur et `runId` en tête du dossier.
- Section de traçabilité reprenant les sources du modèle.

## Écarts assumés

- **PDF reporté.** Le plan autorisait un premier livrable Markdown ; le PDF
  passera par l'impression de la webview, sans seconde chaîne de calcul.
- **Téléchargement Markdown via la webview.** Le bouton produit un fichier
  `text/markdown` téléchargé par le navigateur/webview. Une boîte de dialogue
  d'enregistrement native (`tauri-plugin-dialog`) est laissée à la phase 16 ;
  elle ne changerait ni le contenu ni le déterminisme du dossier.
- **Pack `2026.2` non signé.** Le modèle épingle `2026.1` pour rester
  reproductible et vérifiable hors ligne.
- **Test utilisateur non réalisé.** Le parcours est couvert par des tests
  automatisés (import, ouverture, parcours, export), mais la mesure « premier
  résultat en moins de deux minutes » reste à faire avec 3–4 personnes.

## Vérifications

```powershell
npm run protocol:check
npm run typecheck
npm test
npm run sidecar:test
npm run sidecar:lint
npm run reporting:test
npm run reporting:lint
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
```

Les tests sidecar couvrent l'import (brief, scénario, version, branche),
l'absence de partage entre deux imports, le déterminisme du dossier et
l'absence de fuite de chemins ou de clés.
