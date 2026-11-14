# ADR 0012 — Dataviz maison et panneaux du cockpit

- **Statut** : accepté
- **Date** : 2026-11-14
- **Contexte** : phase 01, s'applique en phases 08–11

## Décision

Le cockpit **conserve et étend** `@see/ui/viz`. Il n'introduit ni ECharts, ni uPlot, ni dockview.

- Graphiques : SVG et canvas maison, alimentés par les tokens (`packages/ui/scripts/generate-tokens.mjs`) et protégés par `npm run ui:check`.
- Nouveaux composants : `FanChart` (éventail P10–P90), `Heatmap` (canvas), `Tornado` (barres divergentes réutilisées), histogrammes mensuels.
- Panneaux : `PanelGrid` maison avec trois zones redimensionnables (hypothèses, principal, secondaire), poignées clavier/souris et presets `Analyse`, `Pilotage`, `Présentation`.
- Plein écran par panneau ; pas de réorganisation arbitraire ni de docking.
- Budget de bundle : le chunk initial de l'UI reste sous **350 Kio gzip** ; un chunk 3D (phase 14) est chargé à part et plafonné à 1,2 Mio gzip.

## Contexte et raisons

- La refonte UI de la v2 a déjà construit un socle cohérent : `LineChart`, `Histogram`, `BarChart`, `DivergingBars`, `Sparkline`, `Legend`, `scale`, `chart.css`, avec tokens et règles d'accessibilité.
- `ui:check` interdit les couleurs en dur et les classes mortes ; changer de librairie reviendrait à contourner ce garde-fou.
- Le besoin réel est de **redimensionner** des panneaux et de choisir une disposition, pas de réorganiser librement des fenêtres. dockview apporte un moteur de docking lourd pour un besoin absent.
- ECharts/uPlot ajoutent des centaines de Kio, leur propre modèle de thème et une accessibilité à recâbler.
- Les graphiques du cockpit sont simples (36 points, 15×15 cellules, 20–30 bins) : SVG/canvas maison suffit largement.

## Alternatives

- **ECharts** : riche, mais lourd, thème parallèle, risque de rupture avec les tokens.
- **uPlot** : très rapide pour de grandes séries, inutile ici (36 points) et pauvre en accessibilité.
- **dockview** : docking complet, complexité et surface de bugs pour un besoin de presets.
- **Recharts/Visx** : ajoute une dépendance React et un style propre, sans bénéfice mesuré.

## Conséquences

- Chaque nouveau graphique doit être testé en géométrie pure (échelles, chemins) et en accessibilité (tableau alternatif, clavier).
- Les performances sont mesurées en phase 09 : FanChart ≤ 16 ms, partiel ≤ 4 ms, 30–60 i/s pendant le glissement.
- Toute proposition de changer de librairie devra fournir : gain mesuré (fps/bundle), respect des tokens, accessibilité équivalente, coût de migration. Sans ces preuves, la décision reste.
- La heatmap utilise un canvas (225 cellules et plus) ; le FanChart reste en SVG (36 points).
- Aucune couleur ne porte seule une information : légende, libellé ou motif obligatoire.

## Vérification

- `npm run ui:check` et `npm run typecheck` verts.
- Tests de géométrie (`fanPath`, échelles, bornes) et de clavier.
- Mesure du bundle avant/après chaque ajout majeur.
- Revue design sur les captures des trois presets.
