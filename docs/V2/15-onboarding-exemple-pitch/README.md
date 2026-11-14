# Phase 15 — Onboarding, projet d'exemple & mode pitch

> **Objectif** : un inconnu ouvre l'application et obtient un premier résultat crédible en moins de deux minutes, puis peut exporter un dossier propre pour présenter son projet.

**Références** : `V3-COCKPIT.md` §10 (D1, D2), §13 ; plan maître §7.
**Dépend de** : phases 09 (cockpit), 11 (analyse), 12 (explication), 13 (versions).
**Débloque** : 16 (lancement).
**Profil** : produit + intermédiaire UI ; 7–8 jours.

---

## 1. Contexte

La v2 n'a pas de parcours d'accueil ni de projet d'exemple complet. `export_report` produit un Markdown minimal (JSON brut), sans mise en forme décisionnelle. Pour janvier, il faut :

- un **projet d'exemple** réaliste, sourcé, sans nouveau modèle sectoriel ;
- un **parcours guidé** court ;
- un **dossier de pitch** déterministe, sans invention de chiffres.

## 2. Périmètre

**Inclus**

- Projet d'exemple « dépôt de revente » basé sur `retail_depot` et un pack de benchmarks existant.
- Import du modèle depuis l'accueil, avec données pré-remplies.
- Parcours guidé en 4–5 étapes, skippable, sans IA obligatoire.
- Mode pitch : rapport structuré (Markdown, PDF si possible).
- Textes de transparence.
- Tests hors ligne et sur profil vierge.

**Exclu**

- Nouveaux modèles sectoriels.
- Narration LLM globale (facultative, via phase 12).
- Cloud/partage.

## 3. Livrables

- [ ] `data/examples/retail-depot-bangui/` (scénario, brief, événements, seed, notes).
- [ ] Commande/import « Créer le projet d'exemple ».
- [ ] `components/onboarding/GuidedTour.tsx` + étapes.
- [ ] `packages/reporting/` ou service `report.build` déterministe.
- [ ] Export Markdown + PDF (via impression web ou moteur PDF local).
- [ ] Textes de transparence et mentions légales provisoires.
- [ ] Tests et captures.

## 4. Tâches détaillées

### Lot A — Projet d'exemple

- [ ] Choisir un pack existant (`cf-bangui-retail-2026.1` ou `cg-brazzaville-retail-2026.1`) et vérifier sa signature/validité.
- [ ] Construire un scénario 36 mois avec :
  - hypothèses réalistes et **sourcées** (provenance benchmark) ;
  - fourchettes prudentes ;
  - 2–3 événements de démonstration ;
  - graine 42 ;
  - une version nommée « Scénario de départ » et une branche « Prix -10 % ».
- [ ] Vérifier que les résultats sont pédagogiques : point mort atteignable, trésorerie tendue mais pas absurde, probabilité de perte non nulle.
- [ ] Documenter les choix et les limites dans `data/examples/retail-depot-bangui/README.md`.
- [ ] Import : `project.createFromTemplate` ou équivalent, avec IDs neufs.
- [ ] Ne pas embarquer de données personnelles ni de secret.
- [ ] Test : import sur profil vierge, offline, < 2 s.

### Lot B — Parcours guidé

- [ ] Étapes :
  1. « Voici vos hypothèses » → panneau d'hypothèses, montrer la source benchmark.
  2. « Bougez un prix » → démonstration du recalcul et de la fourchette.
  3. « Lisez le point mort » → KPI + FanChart + graine.
  4. « Ajoutez un imprévu » → événement simple.
  5. « Exportez votre dossier » → mode pitch.
- [ ] L'overlay ne bloque pas l'interface ; bouton « Passer ».
- [ ] Progression mémorisée ; réinitialisable.
- [ ] Fonctionne sans fournisseur IA.
- [ ] Objectif : premier résultat en < 2 min, mesuré lors des tests utilisateurs.
- [ ] Accessible au clavier, `Échap` ferme.

### Lot C — Rapport déterministe

- [ ] Créer un builder (Python ou TS) qui reçoit les agrégats **du moteur** et produit :
  - page de garde : projet, date, graine, version moteur ;
  - hypothèses et sources ;
  - scénarios/branches et différences ;
  - résultats : P10/P50/P90, point mort, financement, trésorerie ;
  - sensibilité (tornado) ;
  - événements ;
  - méthodologie et limites ;
  - avertissement « simulation basée sur vos hypothèses, pas une prévision garantie ».
- [ ] Aucun chiffre calculé par le rapport : uniquement formaté.
- [ ] Aucun secret, aucun chemin local, aucune clé.
- [ ] Export Markdown ; PDF via `window.print()` (mode webview) ou bibliothèque locale si nécessaire.
- [ ] Si la phase 09 (rapports de la v2) n'est pas terminée, livrer la version minimale Markdown et le noter.
- [ ] Test snapshot : mêmes entrées → même sortie (hors date).

### Lot D — Transparence et contenus

- [ ] Mention visible : « simulation basée sur vos hypothèses, pas une prévision garantie ».
- [ ] Expliquer ce qui part vers le fournisseur IA choisi (phase 12).
- [ ] Politique de confidentialité et CGU provisoires (phase 16 finalise).
- [ ] Aide contextuelle : point mort, fourchette, graine, convergence.

### Lot E — Tests

- [ ] Profil vierge → import → premier résultat < 2 min (test manuel chronométré).
- [ ] Parcours skippable et accessible.
- [ ] Rapport : contenu exact, pas de secret, mention de transparence.
- [ ] Offline complet (pas de provider).
- [ ] Import/export du projet d'exemple.
- [ ] Les chiffres du rapport sont identiques à ceux du cockpit (même run).
- [ ] Test utilisateur (3–4 personnes) consigné.

## 5. Contrats

```ts
type ReportInput = {
  project: { name: string; currency: string; sector?: string };
  scenario: Scenario;
  run: SimulationAggregates;
  branches: BranchSummary[];
  versions: VersionSummary[];
  seed: number;
  engineVersion: string;
  generatedAt: string;
};
```

Règles :

- Le rapport est **déterministe** : mêmes entrées (hors date) → même sortie.
- Le rapport ne lance aucun calcul.
- Toute affirmation chiffrée est traçable à un run.
- Le mode pitch ne dépend pas d'un fournisseur IA.

## 6. Pièges

- **Projet d'exemple irréaliste** : il détruit la confiance ; faire relire par le métier.
- **Benchmarks non sourcés** : afficher la provenance et la fraîcheur.
- **Parcours trop long** : 5 étapes maximum, skippable.
- **Rapport qui recalcule** : risque d'incohérence avec le cockpit.
- **PDF coûteux** : commencer par Markdown + impression.
- **Données personnelles dans le modèle** : aucune.
- **Promesse de prévision** : mention obligatoire.

## 7. Critères d'acceptation

- [ ] Un nouvel utilisateur obtient un résultat en < 2 min sans aide.
- [ ] Le projet d'exemple est sourcé, cohérent et pédagogique.
- [ ] Le parcours est accessible et skippable.
- [ ] Le rapport contient toutes les sections et la mention de transparence.
- [ ] Aucun secret, aucune donnée personnelle.
- [ ] Fonctionne hors ligne.
- [ ] Test utilisateur réalisé.

## 8. Performance

- Import du modèle < 2 s.
- Ouverture du cockpit avec résultat pré-calculé < 1 s.
- Génération du rapport < 1 s (Markdown), < 5 s (PDF).
- Taille du modèle < 1 Mo.

## 9. Risques

| Risque | Mitigation |
|---|---|
| Modèle d'exemple contesté | Relecture métier, sources |
| Parcours ignoré | Court, skippable, mesuré |
| Rapport incohérent | Builder sans calcul, snapshot |
| PDF complexe | Markdown d'abord |
| Temps insuffisant | Mode pitch minimal (Markdown) |

## 10. Definition of Done

- [ ] Projet d'exemple importable et documenté.
- [ ] Parcours guidé livré.
- [ ] Rapport déterministe Markdown (+ PDF si possible).
- [ ] Transparence affichée.
- [ ] Tests utilisateurs consignés.
