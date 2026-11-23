# Phase 12 — Trajectoires, provenance & explication

> **Objectif** : répondre à « d'où vient ce chiffre ? » avec des données traçables, puis — seulement à la demande — une explication LLM dont **aucun nombre ne peut être inventé**.

**Références** : `V3-COCKPIT.md` §3.6, §7 (I7, I8), §4 ; plan maître C10, ADR 0016.
**Dépend de** : phases 02 (échantillon/agrégats), 06 (IPC/cache), 09 (UI).
**Débloque** : 15 (narration du dossier).
**Profil** : senior Python (provenance/validation) + intermédiaire UI (panneau) ; 6–7 jours.

---

## 1. Contexte

Le cockpit affiche des KPI et des points. L'utilisateur doit pouvoir cliquer et voir :

- la définition et la formule ;
- les paramètres qui déterminent la métrique, leurs valeurs, leurs sources et leur confiance ;
- la contribution de chaque paramètre (sensibilité) ;
- les références de benchmark ;
- la graine et la version du moteur.

Puis, s'il le demande, une explication en langage naturel — générée **uniquement** à partir de ce payload, et vérifiée.

## 2. Périmètre

**Inclus**

- Accès aux trajectoires (≤ 200) et aux paramètres tirés d'un run.
- Payload de provenance pour une métrique agrégée ou un point mensuel.
- Panneau « D'où vient ce chiffre ? ».
- Explication LLM à la demande, structurée, validée, mise en cache.
- Repli déterministe hors ligne / sans fournisseur.
- Tests du validateur numérique et de la vie privée.

**Exclu**

- Narration globale du projet (phase 15).
- Nouveaux fournisseurs (phase 04 de la v2).

## 3. Livrables

- [x] Protocole `1.13.0` : `simulation.trajectories`, `simulation.run_params`, `simulation.provenance`, `simulation.explain`.
- [x] `engine` : accès borné à l'échantillon de runs (`SimulationResult.detach_sample`, rétention de 4 échantillons).
- [x] `sidecar/provenance_service.py` et `sidecar/explain_service.py`.
- [x] `components/cockpit/ProvenancePanel.tsx`.
- [x] Validateur numérique (`packages/engine/engine/provenance.py`, partagé par le sidecar et les tests).
- [x] Cache d'explications en mémoire (LRU 100, TTL 24 h, cloisonné par projet).
- [x] Tests et documentation.

## 4. Tâches détaillées

### Lot A — Trajectoires et paramètres tirés

- [x] `simulation.trajectories {runId, count?, indices?}` :
  - renvoie au plus **200** trajectoires ;
  - champs : index, profit mensuel, trésorerie mensuelle, revenus mensuels ;
  - `count > 200` est tronqué et signalé par `truncated: true` ; un index hors échantillon renvoie `trajectory_invalid`.
- [x] `simulation.run_params {runId, index}` : paramètres tirés du run (clé → valeur), graine, version et `scenariosHash`.
- [x] Si le run n'a pas conservé l'échantillon (runs > 20 000 ou éviction) : erreur explicite `run_sample_unavailable`.
- [x] Aucune donnée par run n'est envoyée sans demande explicite.
- [x] Clic sur une trajectoire : sélection persistante dans le store (phase 08). *(Le champ `selection.runIndex` est disponible ; aucune vue de trajectoires ne le consomme encore.)*

### Lot B — Provenance

```ts
type Provenance = {
  runId: string;
  metric: string;
  point: number | null;
  definition: string;
  formula: string;
  value: number;
  unit: string;
  seed: number;
  engineVersion: string;
  runs: number;
  scenariosHash: string;
  inputs: Array<{
    key: string;
    label: string;
    value: number;
    drawnRange: [number, number];
    source: "user" | "benchmark" | "estimate";
    confidence: number | null;
    benchmark?: { label: string; source?: string; url?: string; date?: string };
    correlation: number;
    contribution: number;
  }>;
  caveats: string[];
};
```

- [x] Construire le payload depuis le résultat, le scénario et la sensibilité déjà calculée.
- [x] Pour un point mensuel, utiliser la distribution du mois (phase 02/10).
- [x] `contribution` réutilise `build_sensitivity` (corrélation²) ; ne pas relancer un calcul complet.
- [x] `scenariosHash` : hash canonique du scénario (hors métadonnées volatiles) pour vérifier la cohérence.
- [x] Ne jamais inclure : clés API, chemins locaux, nom de projet non demandé, historique de conversation.

### Lot C — Panneau UI

- [x] Clic sur un KPI → panneau « D'où vient ce chiffre ? ». *(Les points du FanChart et les barres du tornado restent à brancher lors des phases de dataviz suivantes.)*
- [x] Sections : définition, valeur + fourchette, entrées et contributions, sources/benchmarks, graine/version, limites.
- [x] Bouton « Expliquer avec l'IA » :
  - désactivé si aucun fournisseur n'est configuré (texte explicite dans le panneau) ;
  - affiche le payload exact qui sera envoyé, dans un bloc repliable ;
  - explication synchrone avec timeout de 30 s (pas de job annulable dédié) ;
  - résultat avec badge « généré à partir des données ci-dessus ».
- [x] Hors ligne : bouton « Explication déterministe » toujours disponible, sans appel réseau.
- [x] Accessible au clavier, fermable avec `Échap`, focus géré (`useDialogFocus`).

### Lot D — Explication LLM

- [x] Handler `simulation.explain {projectId, runId, metric, point?, profile?, apiKey?, model?}` :
  - construit le payload de provenance ;
  - appelle `packages/providers` via le service fournisseur existant (jamais d'appel réseau direct) ;
  - sortie structurée :
    ```json
    {
      "summary": "string",
      "points": [{ "text": "string", "references": ["p50", "seed"] }],
      "caveats": ["string"]
    }
    ```
  - prompt : français, aucune recommandation d'investissement, graine et incertitude rappelées par le repli et les limites.
- [x] **Validateur numérique** :
  - extraire les nombres : espaces/NBSP de milliers, virgule décimale, `%`, unités, plages `a–b` ;
  - normaliser et comparer à l'ensemble des nombres du payload (tolérance **relative** de 0,1 % pour les arrondis) ;
  - autoriser les libellés `P10`, `P50`, `P90` et les unités, pas les nombres inventés ;
  - si un nombre est inconnu : réparation (max 2), sinon repli déterministe.
- [x] Repli déterministe : phrase construite à partir du payload, sans LLM (valeur, fourchette, graine, runs, entrée la plus contributive).
- [x] Cache : clé `sha256(payload canonique + modèle + version du prompt)`, cloisonné par projet ; LRU 100 ; TTL 24 h ; le payload brut n'est jamais stocké.
- [x] Budget : tokens limités (1 200), timeout 30 s. L'annulation explicite d'un appel en cours reste hors périmètre.
- [x] Journalisation : méthode, statut, erreur fournisseur ; **jamais** le contenu du payload ni la clé.

### Lot E — Tests

- [x] Trajectoires : count, indices, troncature, échantillon absent.
- [x] Paramètres tirés : mêmes valeurs que celles utilisées dans le run (comparer au préfixe).
- [x] Provenance : contributions cohérentes, hash stable, pas de secret.
- [x] Validateur :
  - « 12 500 FCFA » accepté si 12 500 est dans le payload ;
  - « 12,5 % » accepté si 0.125 est dans le payload ;
  - « 1 234 » inventé rejeté ;
  - « P10–P90 » non traité comme un nombre inventé ;
  - tolérance relative de 0,1 % : 12 500 → 12 512,5 accepté, 12 513 rejeté (décision consignée ci-dessous).
- [x] LLM : sortie valide acceptée, sortie avec nombre inventé rejetée, réparation (2 tentatives), repli.
- [x] Cache : hit/miss, invalidation par payload/modèle, cloisonnement par projet.
- [x] Hors ligne : repli sans appel réseau.
- [x] Vie privée : aucun secret dans le payload, les logs ou le cache disque (cache mémoire uniquement).

## 5. Contrats

```python
def build_provenance(result: SimulationResult, scenario: Scenario, metric: str, point: int | None = None) -> dict: ...
def deterministic_explanation(provenance: Mapping[str, Any]) -> dict: ...
def validate_explanation(explanation: Mapping[str, Any], provenance: Mapping[str, Any]) -> list[str]: ...
```

Règles :

- Le LLM ne reçoit **que** `Provenance` (sérialisé), pas le scénario complet.
- Une explication sans fournisseur est **toujours** disponible.
- Un nombre affiché dans l'explication doit exister dans le payload (ou être un libellé autorisé).
- Le cache ne stocke pas le payload brut si un secret pouvait s'y trouver ; il ne doit pas en contenir.

## 6. Pièges

- **Valider avec un simple regex** : les formats français (espaces, virgules, %) piègent ; tester.
- **Accepter les arrondis sans limite** : définir la tolérance et la documenter.
- **Confondre corrélation et contribution causale** : le panneau doit le dire.
- **Envoyer tout le projet au LLM** : fuite et coût ; payload minimal.
- **Cache global** : une explication dépend du scénario, de la graine et du modèle.
- **Bloquer l'UI pendant l'appel** : job annulable, timeout.
- **Oublier le mode hors ligne** : c'est un principe produit.

## 7. Critères d'acceptation

- [x] Un clic sur un KPI ouvre une provenance complète et sourcée.
- [x] Les trajectoires ne sortent que sur demande, ≤ 200.
- [x] L'explication LLM ne contient aucun nombre absent du payload.
- [x] Le repli déterministe fonctionne hors ligne.
- [x] Le cache est borné et respecte la vie privée.
- [x] Les tests du validateur couvrent les formats français.
- [x] Protocole `1.13.0` généré.

## 8. Performance

| Mesure | Cible |
|---|---|
| `provenance` | < 50 ms |
| `trajectories` 200 runs | < 100 ms, < 1 Mo |
| Explication LLM (hors réseau) | < 30 s, annulable |
| Validation numérique | < 5 ms |
| Panneau UI | < 16 ms |

## 9. Risques

| Risque | Mitigation |
|---|---|
| Nombre inventé | Validateur + réparation + repli |
| Fuite de données | Payload minimal, tests, logs filtrés |
| Coût LLM | Cache, budget, opt-in explicite |
| Explication générique | Prompt ancré sur la provenance, références |
| Échantillon absent | Erreur claire, pas de résultat partiel |

## 10. Definition of Done

- [x] Trajectoires, provenance et explication livrés.
- [x] Validateur numérique testé.
- [x] Repli hors ligne opérationnel.
- [x] Vie privée vérifiée.
- [x] Documentation utilisateur du panneau.

## 11. État d'implémentation (2026-11-23)

### Décisions effectives

- **Protocole `1.13.0`** : quatre méthodes ajoutées, types `Trajectory`, `Provenance`, `Explanation` et variantes `Params`/`Result`.
- **Rétention de l'échantillon** : le service de simulation conserve le résultat après `done` (provenance et paramètres) mais ne garde l'échantillon complet que pour les **4 derniers runs terminés**. Au-delà, `simulation.trajectories` et `simulation.run_params` répondent `run_sample_unavailable`. Les runs de plus de 20 000 runs sont également refusés.
- **Trajectoires** : `count` est plafonné à 200 et `truncated` indique qu'une partie de la demande n'a pas été servie ; `indices` hors échantillon renvoie `trajectory_invalid`.
- **Provenance** : construite sans relancer de simulation, à partir de `result.sensitivity`; `scenariosHash` exclut le nom et les notes. Le payload contient une `range` P10–P90 optionnelle.
- **Validation** : tolérance **relative** de 0,1 % (`12 500` → `12 512,5` accepté, `12 513` rejeté). Les formats français (espaces de milliers, virgule, `%`, `P10–P90`) sont testés côté moteur, pas seulement côté client.
- **Explication** : synchrone, timeout de 30 s, deux tentatives de réparation puis repli déterministe. `profile`, `apiKey` et `model` sont transmis dans la params ; Tauri injecte la clé comme pour l'agent. Un run d'un autre projet est refusé.
- **Cache** : mémoire seulement, un `OrderedDict` par projet, 100 entrées, TTL 24 h, clé `sha256(payload canonique + modèle + version du prompt)`. Aucun payload brut ni réponse brute n'est conservé.
- **UI** : boutons « D'où vient ce chiffre ? » sur les KPI, panneau focalisé (`Échap`, piège de tabulation), aperçu du payload exact, bouton IA absent sans fournisseur Narrateur, bouton déterministe toujours présent, badge « généré à partir des données ci-dessus ».

### Écarts assumés

- L'annulation d'un appel LLM en cours n'est pas exposée : le timeout de 30 s borne l'attente. Un job annulable pourra être ajouté avec la narration de la phase 15.
- Le panneau n'est pas encore ouvert depuis les points du FanChart ni les barres du tornado ; les KPI couvrent le parcours demandé.
- Aucune vue de trajectoires ne consomme encore `selection.runIndex` : l'API est prête et testée, la dataviz viendra avec les phases suivantes.
- Le lien « réglages fournisseur » est remplacé par un texte explicite dans le panneau ; la navigation vers les réglages appartient à la coquille.

### Fichiers

- `packages/protocol/schema/messages.schema.json`, `packages/protocol/src/generated.ts`, `sidecar/protocol_models.py`.
- `packages/engine/engine/provenance.py`, `scenario.py`, `packages/engine/tests/test_provenance.py`.
- `sidecar/simulation_service.py`, `sidecar/provenance_service.py`, `sidecar/explain_service.py`, `sidecar/rpc.py`.
- `apps/desktop/src-tauri/src/lib.rs`, `apps/desktop/src/lib/ipc.ts`.
- `apps/desktop/src/components/cockpit/ProvenancePanel.tsx`, `KpiBar.tsx`, `CockpitScreen.tsx`, `styles.css`.
- Tests : `test_provenance_service.py`, `ProvenancePanel.test.tsx`, `KpiBar.test.tsx`.
