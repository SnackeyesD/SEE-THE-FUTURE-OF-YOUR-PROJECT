# ADR 0007 — Parcours MVP, UI locale et graphiques moteur

## Statut

Accepté — phase 06.

## Contexte

La phase 06 doit livrer un vertical slice utilisable : idée, entretien, brief,
hypothèses, simulation, résultats et narration. L'application doit rester
local-first, fonctionner sans cloud, consommer les contrats typés du protocole
et ne jamais recalculer un chiffre dans l'interface.

## Décision

### État et navigation

- L'état du parcours reste local à `App.tsx` : vue active, projet actif, données
  projet, session d'agent, permissions en attente, progression et narration.
- Pas de routeur ni de client de requêtes : les écrans sont des composants
  contrôlés, montés selon la vue. Cela réduit les dépendances et le risque de
  désynchronisation avec le sidecar.
- Après chaque action qui modifie le projet (tour d'agent, brief, scénario,
  simulation), `refreshWorkspace` recharge de façon atomique les données projet,
  la session et les rôles via `project.data`, `agent.state` et `agent.roles`.
- La vue proposée à l'ouverture est déduite des données persistées : résultats,
  puis simulation, puis hypothèses, puis brief, puis entretien.

### Design system

- `packages/ui` expose un design system minimal sans dépendance runtime :
  cartes, boutons, champs, badges, alertes, statistiques, progression, états
  vides et contexte de densité.
- Les styles vivent dans `apps/desktop/src/styles.css`, avec des jetons CSS pour
  les couleurs, surfaces et bordures. Le rendu reste lisible sur un PC modeste.
- L'accessibilité de base est assurée : libellés associés aux champs, focus
  visible, rôles `log`, `status`, `progressbar` et textes alternatifs des SVG.

### Graphiques

- Les trois graphiques (histogramme du profit, tornade de sensibilité, courbe
  mensuelle) sont des SVG écrits localement, sans Recharts ni visx.
- Motifs : aucune dépendance réseau ou runtime supplémentaire, contrôle total
  des valeurs affichées, bundle réduit et rendu déterministe hors ligne.
- Les composants reçoivent exclusivement `ProjectDataResult.run.result` ou des
  sous-objets issus du moteur. Aucun percentile, agrégat ou sensibilité n'est
  recalculé côté UI.
- Chaque marqueur et chaque point porte un titre accessible ; les axes et
  unités sont formatés avec `Intl` selon la devise du scénario.

### Persistance et IPC

- Le protocole passe à `1.5.0` et ajoute `project.data`,
  `project.brief.save`, `project.scenario.save`, `project.simulate`.
- Le sidecar conserve un service projet dédié. Il valide les briefs et scénarios
  avec les modèles du moteur et avance la session d'agent vers l'avant
  uniquement (`brief_draft`, `brief_validated`, `hypotheses_set`,
  `results_ready`).
- `project.simulate` émet `simulate.progress` sous forme de notifications
  JSON-RPC. Le shell Rust les relaie en `simulation:progress` et applique un
  timeout de 600 s à cette méthode.
- Les types IPC restent générés depuis `packages/protocol` ; aucun type de
  commande n'est dupliqué à la main.

### Narration

- La narration est demandée à l'agent avec le rôle `narrator` et le résultat
  structuré du moteur comme contexte.
- Le texte est affiché séparément des chiffres calculés.
- `verifyNarration` extrait les nombres du texte et les compare à l'ensemble des
  valeurs autorisées du résultat. Un nombre inconnu déclenche un avertissement
  visible et invite à régénérer la narration.
- La narration n'est pas encore persistée ni exportée : elle est conservée en
  mémoire jusqu'au changement de run ou de projet.

### Offline, coûts et i18n

- Aucune étape du parcours ne requiert le cloud : la simulation est locale et
  Ollama peut servir de fournisseur sans clé.
- Le coût et le plafond restent gérés dans le panneau fournisseurs ; la
  simulation n'appelle aucun fournisseur IA.
- Le français est la langue par défaut et le FCFA la devise par défaut.
- La bascule FR/EN est persistée et traduit les libellés de navigation. La
  traduction complète des écrans est différée.

## Conséquences

- Le parcours est testé au niveau protocole, sidecar, stockage et shell Rust ;
  l'exécution manuelle de l'application Tauri et le test utilisateur restent à
  faire avant une décision GO.
- Le streaming token par token, l'annulation des opérations longues, la
  persistance de la narration et l'i18n complète sont explicitement différés.
- Toute évolution des écrans doit continuer à puiser ses chiffres uniquement
  dans le résultat du moteur et à passer par les contrats `project.*` / `agent.*`.
