# V3 : Cockpit de simulation

Spécification pour Claude Code. À placer à la racine du dépôt, à côté de `ARCHITECTURE-DESKTOP.md`, `PLAN-IMPLEMENTATION.md` et `CLAUDE.md`.

> **Objectif** : transformer l'espace où apparaissent les données simulées en **cockpit interactif** où l'utilisateur pilote la simulation en direct (« je bouge, ça réagit »), avec des vues avancées dont une **prévisualisation 3D**, et rendre l'application prête pour un **lancement début janvier 2027**.

---

## 0. Consignes de départ pour Claude Code

1. **Commencer par un audit de l'existant** (tâche V3-0) : lire le dépôt, le sidecar, `packages/engine`, `packages/protocol`, `packages/ui`, `apps/desktop/src`, les ADR existants. Les noms de fichiers, de méthodes et de composants cités ci-dessous sont des **intentions** : les adapter à la réalité du code, sans casser l'existant.
2. Ne pas réécrire ce qui fonctionne. Étendre, puis refactorer seulement si l'audit le justifie (consigner dans un ADR).
3. Travailler **par tranches verticales livrables** (voir §10), chacune testée et utilisable.
4. Respecter toutes les règles de `CLAUDE.md` (§11 en ajoute de nouvelles).

## 1. Contexte et principes

La v2 est fonctionnelle : app Tauri 2 + UI React, sidecar Python (JSON-RPC NDJSON sur stdio), moteur Monte Carlo (`packages/engine`), persistance SQLite/`.simproj`, fournisseurs IA BYOK, agent, sandbox Pyodide. Le principe fondateur reste : **le LLM comprend et explique, le moteur calcule**. Aucun chiffre ne naît dans l'UI ni dans le LLM.

Principes V3 :
- **Réactivité d'abord** : sans moteur rapide et stable, aucune interaction n'est crédible.
- **Honnêteté de l'incertitude** : toujours des fourchettes, jamais un chiffre isolé ; pas d'animation qui suggère une fausse précision.
- **Tout est annulable** (annuler/refaire) et **reproductible** (graine visible).
- **La 3D est un complément**, jamais la seule façon de voir une information.
- **Dégradation élégante** : l'app reste agréable sur un PC modeste.

## 2. Périmètre

**Inclus** : moteur réactif, cockpit 2D, interactions de pilotage, événements, recherche d'objectif, explications au clic, comparaison de scénarios, vue 3D (surface + nuage), onboarding avec projet d'exemple, durcissement pré-lancement.

**Exclu de la V3** : synchronisation cloud, multi-utilisateur, application mobile, nouveaux modèles sectoriels (hors celui du projet d'exemple), exécution de scripts supplémentaires.

## 3. Moteur : rendre la simulation interactive (`packages/engine`)

### 3.1 Tirages communs et reproductibles (CRN)

Objectif : quand l'utilisateur déplace un curseur, **seul l'effet de ce paramètre change**, sans « tremblement » des courbes.

- Générer les nombres aléatoires de base **indépendamment des paramètres** : uniformes U(0,1) et normales standard Z, par run et par « emplacement » (paramètre, mois). Les paramètres transforment ces tirages : triangulaire via l'inverse de sa fonction de répartition (forme fermée), normale/log-normale via `moyenne + écart_type × Z`.
- **Propriété de préfixe** : les `n` premiers runs d'un calcul à `N` runs doivent être **identiques** à un calcul à `n` runs (même graine). Implémentation suggérée : générer par blocs de taille fixe (ex. 250 runs), chaque bloc dérivé de `SeedSequence(seed)` par son indice de bloc.
- Mettre en cache les tirages de base par `(seed, structure du modèle, nombre de blocs)` ; invalider uniquement si la structure change.
- Pas de dépendance à `scipy` sans ADR (numpy seul pour le moteur).

### 3.2 Calcul progressif et annulable

```python
simulate(params, events, n_runs, horizon_months, seed,
         on_progress=None, cancel=None) -> SimulationResult
```

- Calcul par blocs ; `on_progress(blocs_faits, total, résumé_partiel)` après chaque bloc.
- `cancel` (jeton coopératif) vérifié entre blocs ; annulation en moins de 100 ms.
- Deux niveaux de qualité : `draft` (≈ 500 runs) pendant le geste, `final` (≈ 5 000 runs) au relâchement.
- **Indicateur de convergence** : stabilité des percentiles P10/P50/P90 et du point mort d'un bloc au suivant (ex. variation relative < 1 %).

### 3.3 Événements (chocs)

```json
{ "id": "ev1", "type": "supplier_price_rise", "start_month": 5, "duration": 3,
  "target": "cout_achat", "mode": "multiplicative",
  "magnitude": { "dist": "triangular", "min": 1.05, "mode": 1.15, "max": 1.30 },
  "probability": 1.0 }
```

- Les événements modifient des paramètres **dans le temps** (multiplicatif ou additif), éventuellement avec une probabilité d'occurrence (tirée avec les tirages de base, donc compatible CRN).
- Catalogue initial (à valider avec le secteur du projet d'exemple) : hausse du prix fournisseur, rupture de stock, arrivée d'un concurrent, coupure d'électricité prolongée, choc de change, période de forte demande, perte d'un client majeur.

### 3.4 Recherche d'objectif (goal seek)

- Entrée : métrique cible (ex. `P(point_mort <= 6 mois) >= 0.7`), leviers autorisés avec bornes, contraintes éventuelles.
- Grâce aux tirages communs, la métrique est **déterministe** : 1 levier → dichotomie ; plusieurs leviers → recherche par coordonnées ou Nelder-Mead avec `draft`, puis confirmation en `final`.
- Sortie : valeurs proposées, métrique obtenue, **si l'objectif est atteignable** (sinon message clair et meilleur compromis).

### 3.5 Surface de résultat (vue 2D/3D)

```python
surface(params, axis_x, axis_y, metric, grid=(25, 25), n_runs=300, seed) -> SurfaceResult
```

Retourne `z_p50` (et optionnellement `z_p10`, `z_p90`), les axes et la position du point courant. Vectoriser sur la grille ; budget en §9.

### 3.6 Données par run et traçabilité

- Les résultats **par run** restent dans la mémoire du sidecar (cache par `run_id`, taille bornée) ; l'UI ne reçoit par défaut que des **agrégats**.
- Accès à la demande : trajectoire d'un run (`index`), échantillon de ≤ 200 trajectoires, **paramètres tirés** pour un run.
- **Provenance d'une métrique** : liste des paramètres qui la déterminent, leur contribution (sensibilité), leur `source`/`confidence`, références de benchmark.

## 4. Protocole IPC (`packages/protocol`)

Source unique : le schéma JSON ; régénérer les types TS et Python (`protocol:generate`), garder `protocol:check` vert.

Le sidecar doit traiter les requêtes **sans bloquer la lecture de stdio** : calcul dans un thread ou processus de travail, messages sortants sérialisés.

| Méthode (client → sidecar) | Rôle |
|---|---|
| `simulation.start` `{sessionId, scenarioId, overrides, events, quality, seed?}` | Démarre un calcul, renvoie `{runId}`. Un nouveau `start` pour la même `sessionId` **annule** le précédent. |
| `simulation.cancel` `{runId}` | Annule. |
| `simulation.surface` `{…}` | Calcule une surface (progression en notifications). |
| `simulation.goalseek` `{…}` | Recherche d'objectif. |
| `simulation.trajectories` `{runId, count \| indices}` | Trajectoires à la demande. |
| `simulation.run_params` `{runId, index}` | Paramètres tirés d'un run. |
| `simulation.provenance` `{runId, metric, point?}` | Données de provenance pour l'explication. |

| Notification (sidecar → client) | Contenu |
|---|---|
| `simulation.progress` | `runId, completed, total, convergence` |
| `simulation.partial` | agrégats partiels (percentiles, histogrammes, KPI) |
| `simulation.done` | agrégats finaux, `seed`, `engineVersion`, durée |
| `simulation.cancelled` / `simulation.error` | statut ou erreur typée |

Règles : messages d'agrégats compacts (viser < 500 Ko), séries de percentiles sous-échantillonnées si besoin, aucun secret dans les messages ni les logs.

## 5. État et données côté UI (`apps/desktop/src`, `packages/ui`)

### 5.1 Session de cockpit

Store (Zustand ou équivalent déjà utilisé) avec :
- `session` : scénario courant, paramètres en cours d'édition (brouillon), événements, graine, qualité, statut de calcul.
- `runs` : résultats par `runId` (agrégats uniquement) ; **runs épinglés** pour comparaison (fantômes).
- `selection` : mois sélectionné, trajectoire sélectionnée, paramètre focalisé.
- `layout` : disposition des panneaux (persistée par projet).

### 5.2 Annuler / refaire

- Toute modification (paramètre, événement, seuil, verrou, disposition) est une **commande** avec son inverse (patches immer ou équivalent). Pile bornée.
- **Versions nommées** de scénario (instantanés) : nouvelle table `scenario_version` via migration SQLite, incluses dans l'export `.simproj`. Mettre à jour la documentation du format et le test d'import/export.

### 5.3 Recalcul en direct

- Pendant un geste : `simulation.start` en `draft`, annulation du précédent, mise à jour du graphique à chaque `partial`.
- Au relâchement (ou après 400 ms d'inactivité) : `final`.
- Les nombres affichés proviennent **uniquement** des messages du sidecar.

## 6. Interface du cockpit

### 6.1 Disposition

Panneaux **déplaçables et redimensionnables** (évaluer `dockview` ou `flexlayout-react` via ADR). Dispositions prédéfinies : « Analyse », « Pilotage », « Présentation ». Chaque graphique peut passer en plein écran.

```
┌───────────────────────────────────────────────────────────────────┐
│ KPI : P(point mort ≤ N mois) · Financement P50/P90 · P(trésorerie<0)│
│        Convergence ▓▓▓▓▓░ 92 %   ·   Graine 42 ↻   ·   v. moteur    │
├──────────────┬────────────────────────────────┬───────────────────┤
│ Hypothèses   │  Graphique principal           │ Vue secondaire    │
│ (curseurs,   │  (éventail P10–P90, seuil,     │ (tornado, histo   │
│ verrous,     │   fantômes, trajectoires)      │  point mort,      │
│ sources)     │                                │  carte de chaleur,│
│              ├────────────────────────────────┤  3D)              │
│              │ Frise temporelle : curseur de  │                   │
│              │ temps + événements            │                   │
└──────────────┴────────────────────────────────┴───────────────────┘
```

### 6.2 Bibliothèques

- **2D** : Apache ECharts (canvas, zoom, sélection par pinceau, mises à jour fréquentes). Alternative légère pour les séries denses : uPlot (ADR si retenue).
- **3D** : Three.js via `@react-three/fiber` + `drei` (contrôle total et performances). Alternative rapide : Plotly `surface` / `scatter3d` (plus lourd en taille).
- Décisions finales par ADR après un petit banc d'essai sur machine modeste.

### 6.3 Panneau d'hypothèses

Pour chaque paramètre :
- curseur à **trois poignées** (min / mode / max) avec aperçu de la distribution ;
- **verrou** (le paramètre reste fixe) ;
- badges `source` (utilisateur / benchmark / hypothèse) et `confidence` ;
- survol : valeur de référence du benchmark si disponible ;
- double-clic : saisie numérique ; remise à la valeur du benchmark.

## 7. Fonctionnalités d'interaction (avec critères d'acceptation)

| ID | Fonctionnalité | Critères d'acceptation |
|---|---|---|
| I1 | **Recalcul en direct** pendant le glissement d'un curseur | Mise à jour fluide (≥ 50 i/s côté UI) ; pas de tremblement des courbes ; résultat `final` après relâchement ; annulation du calcul précédent. |
| I2 | **Convergence & graine** | Badge de convergence ; graine affichée et modifiable ; bouton « relancer avec une autre graine » ; même graine = mêmes résultats. |
| I3 | **Seuil déplaçable** | Ligne « trésorerie minimale » glissable ; probabilité de passer sous le seuil mise à jour en direct. |
| I4 | **Curseur de temps** | Lecture/pause mois par mois ; au mois sélectionné, distribution de l'état (histogramme) ; raccourcis clavier. |
| I5 | **Événements** | Ajout depuis un catalogue ; placement et durée sur la frise (glisser-déposer) ; intensité réglable ; effet visible sur le graphique ; activable/désactivable. |
| I6 | **Recherche d'objectif** | Formulaire objectif + leviers ; résultat appliqué en un clic comme nouvelle branche ; message clair si inatteignable. |
| I7 | **Trajectoire au clic** | Clic sur la bande ou une trajectoire : affiche la trajectoire et les paramètres tirés ; sélection persistante. |
| I8 | **« D'où vient ce chiffre ? »** | Clic sur un KPI ou un point : panneau de provenance (paramètres, contributions, sources, benchmarks) ; explication LLM **à la demande**, générée uniquement à partir du payload de provenance ; **vérification automatique** qu'aucun nombre n'est inventé ; mise en cache. |
| I9 | **Branches & comparaison** | Dupliquer un scénario ; épingler un run en fantôme ; différence des hypothèses entre deux branches ; comparaison côte à côte. |
| I10 | **Tornado interactif** | Clic sur une barre : focalise le curseur correspondant. |
| I11 | **Carte de chaleur 2 paramètres** | Choix des axes ; clic sur la carte règle les deux paramètres ; courbes de niveau. |
| I12 | **Annuler / refaire / versions** | Ctrl+Z / Ctrl+Y fiables sur toutes les actions listées en §5.2 ; versions nommées restaurables. |
| I13 | **Confort** | Palette de commandes (Ctrl+K), raccourcis (Espace = lecture, flèches = temps, F = plein écran, 1-6 = vues), dispositions mémorisées. |

## 8. Vue 3D

### 8.1 Contenu

1. **Surface de résultat** : métrique (profit à N mois, point mort, besoin de financement) en fonction de deux paramètres. Marqueur du point courant ; **clic = règle les deux curseurs** ; option d'afficher les surfaces P10/P90 en transparence.
2. **Nuage Monte Carlo** : un point par run (ex. investissement × mois de point mort × résultat final), échantillon ≤ 5 000 points, couleur selon le résultat.
3. (Optionnel) **Surface en éventail** : temps × scénarios × percentiles.

### 8.2 Exigences

- Rotation, zoom, réinitialisation de la caméra, mode « top-down » qui revient à la carte de chaleur.
- **Équivalent 2D obligatoire** (carte de chaleur / nuage 2D) et **repli automatique** si WebGL est indisponible ou lent (détection à l'ouverture et mesure du nombre d'images par seconde). Tester en particulier la webview Linux (WebKitGTK) et un PC Windows modeste.
- Accessibilité : aucune information uniquement portée par la 3D ; légende et valeurs lisibles au survol.
- Pas de rendu coûteux hors écran : suspendre la boucle de rendu quand le panneau n'est pas visible.

## 9. Budgets de performance (à mesurer, pas à supposer)

À mesurer sur une machine de référence modeste (ex. processeur de gamme intermédiaire de 2018–2020, 8 Go de RAM, sans GPU dédié) :

| Mesure | Cible |
|---|---|
| Calcul `draft` (500 runs × 36 mois) | ≤ 150 ms |
| Calcul `final` (5 000 runs × 36 mois) | ≤ 1,5 s |
| Annulation d'un calcul | ≤ 100 ms |
| Surface 25 × 25 (300 runs par point) | ≤ 3 s |
| Mise à jour d'un graphique (≤ 5 000 points) | ≤ 16 ms |
| Mémoire du sidecar | ≤ 500 Mo |
| Démarrage de l'application | à mesurer et consigner |

Mettre en place un **banc d'essai reproductible** (`npm run bench`) pour le moteur et un test de fluidité UI ; consigner les résultats dans `docs/perf/`.

## 10. Plan de réalisation

Rythme réaliste : environ 7 semaines. Chaque tâche : code + tests + doc. En cas de retard, **couper dans l'ordre inverse des priorités** (voir §12).

### Tâche V3-0 : Audit et cadrage (1–2 jours)
- Cartographier le code existant et lister les écarts avec cette spec.
- Produire les ADR de décision : CRN et calcul progressif ; protocole de flux ; bibliothèques de graphiques ; 3D et repli ; modèle d'annulation/versions. (Vérifier la numérotation des ADR existants.)
- **Livrable** : `docs/v3/audit.md` + ADR.

### Tranche A : Moteur réactif + cockpit 2D (semaines 1–2)
- A1 : CRN, propriété de préfixe, calcul par blocs, annulation, convergence (§3.1–3.2) + tests.
- A2 : protocole `simulation.*` avec notifications, sidecar non bloquant (§4).
- A3 : store de session, annuler/refaire, recalcul en direct (§5).
- A4 : graphique principal en éventail, KPI, seuil déplaçable, fantômes, panneau d'hypothèses à trois poignées (§6, I1–I3, I9 partiel, I12).
- A5 : banc d'essai de performance (§9).
- **Jalon A** : on déplace un curseur et la courbe réagit de façon fluide et stable. **→ Premier test avec 3 à 4 vrais utilisateurs (voir §13).**

### Tranche B : Pilotage avancé (semaines 3–4)
- B1 : curseur de temps et histogramme au mois sélectionné (I4).
- B2 : événements : moteur + catalogue + frise (I5, §3.3).
- B3 : recherche d'objectif (I6, §3.4).
- B4 : trajectoire au clic, provenance et explication (I7, I8).
- B5 : tornado interactif, carte de chaleur, versions nommées, palette de commandes (I10–I13).
- **Jalon B** : un utilisateur peut dire « je veux le point mort en 6 mois » et obtenir des leviers concrets.

### Tranche C : 3D (semaine 5)
- C1 : `surface()` du moteur + test de performance.
- C2 : vue 3D de la surface avec clic → curseurs, repli automatique sur la carte de chaleur.
- C3 : nuage Monte Carlo 3D (seulement si le temps le permet).
- **Jalon C** : la 3D fonctionne sur la machine de référence, ou le repli 2D se déclenche proprement.

### Tranche D : Pré-lancement (semaines 6–7)
- D1 : **projet d'exemple** (secteur du MVP) avec benchmarks sourcés, et parcours d'accueil guidé (première simulation en moins de 2 minutes).
- D2 : **mode pitch** : export d'un dossier propre (hypothèses, scénarios, sensibilité, besoin de financement) via la phase 09 ; version minimale si la phase 09 n'est pas terminée.
- D3 : installateur Windows **signé**, mises à jour automatiques signées, rapports de crash en opt-in (phase 10 allégée).
- D4 : mentions de transparence : « simulation basée sur vos hypothèses, pas une prévision garantie », politique de confidentialité (ce qui part vers le fournisseur d'IA choisi), CGU.
- D5 : tests de bout en bout des parcours critiques, test sur machine modeste, correction des défauts bloquants.
- **Jalon D** : produit installable, signé, utilisable par un inconnu sans aide.

## 11. Règles supplémentaires pour `CLAUDE.md`

```markdown
## V3 Cockpit
- L'UI ne calcule aucun chiffre de simulation : tout provient des messages du sidecar.
- Toute comparaison (fantômes, branches) utilise la même graine et la même structure de tirages.
- Les `n` premiers runs d'un calcul à N runs sont identiques à un calcul à n runs (test obligatoire).
- Aucune vue 3D sans équivalent 2D ni repli automatique.
- Toute action de l'utilisateur sur le cockpit est annulable (commande avec inverse).
- Les résultats par run ne quittent pas le sidecar sans demande explicite (agrégats par défaut).
- Les explications du LLM sont générées à la demande, uniquement à partir du payload de provenance, et validées (aucun nombre absent du payload).
- Les budgets de performance (§9) sont vérifiés par `npm run bench` ; une régression > 20 % bloque la fusion.
- Ne jamais afficher un résultat sans sa fourchette ni sa graine.
```

## 12. Priorités et ordre de sacrifice

Du plus essentiel au plus facultatif (couper depuis le bas) :
1. Moteur réactif + cockpit 2D (A) : **indispensable**.
2. Pré-lancement : signature, onboarding, projet d'exemple, transparence (D1, D3, D4).
3. Événements, recherche d'objectif, provenance (B2–B4).
4. Curseur de temps, tornado/carte de chaleur interactifs (B1, B5).
5. Mode pitch (D2).
6. Vue 3D surface (C1–C2).
7. Nuage 3D (C3).

## 13. Validation par les utilisateurs (hors code)

Dès le jalon A (semaine 2), puis à chaque jalon :
- **3 à 4 personnes** du public visé (porteur de projet, gérant de commerce), 20 minutes chacune, sans aide.
- Tâches : décrire son projet, lire le point mort, tester une hypothèse (« et si je baisse mon prix ? »).
- Mesurer : temps jusqu'au premier résultat, tâches réussies sans aide, points de confusion, ce qu'ils comprennent de l'incertitude.
- Consigner dans `docs/v3/user-tests.md` ; **les constats peuvent modifier l'ordre du §12**.

## 14. Risques

| Risque | Mitigation |
|---|---|
| Moteur trop lent pour le direct | CRN + `draft` à faible nombre de runs + calcul par blocs ; banc d'essai dès la tranche A |
| Sidecar bloqué par un calcul long | Thread de travail, annulation coopérative, file de messages sortants |
| Webview Linux sans WebGL fiable | Détection, repli 2D, tests sur Pop!_OS/Ubuntu |
| Charge de travail trop élevée pour janvier | Ordre de sacrifice §12 ; 3D en dernier |
| Fausse précision perçue | Fourchettes partout, graine visible, mention de transparence |
| Explications du LLM erronées | Génération sur payload seul + vérification des nombres + cache |
| Antivirus / SmartScreen | Signature tôt (démarrer la démarche immédiatement), test sur VM propre |
| Format `.simproj` cassé par les versions | Migration + test d'import/export de l'ancien et du nouveau format |

## 15. Definition of Done (par tâche)

- [ ] Critères d'acceptation de la tâche cochés.
- [ ] Lint, typecheck, tests unitaires et d'intégration verts ; `protocol:check` vert.
- [ ] Budgets de performance respectés ou dérogation consignée.
- [ ] ADR et documentation à jour.
- [ ] Aucun secret en clair, journalisé ou commité.
- [ ] Fonctionnement hors ligne préservé.
- [ ] Pas de régression sur les phases 01–07 (tests E2E).
