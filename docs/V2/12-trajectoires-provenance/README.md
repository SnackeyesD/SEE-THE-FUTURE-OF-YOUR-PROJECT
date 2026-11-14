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

- [ ] Protocole `1.12.0` : `simulation.trajectories`, `simulation.run_params`, `simulation.provenance`, `simulation.explain`.
- [ ] `engine` : accès borné à l'échantillon de runs.
- [ ] `sidecar/provenance_service.py` et `sidecar/explain_service.py`.
- [ ] `components/cockpit/ProvenancePanel.tsx`.
- [ ] Validateur numérique (`packages/agent-core` ou module partagé).
- [ ] Cache d'explications.
- [ ] Tests et documentation.

## 4. Tâches détaillées

### Lot A — Trajectoires et paramètres tirés

- [ ] `simulation.trajectories {runId, count?, indices?}` :
  - renvoie au plus **200** trajectoires ;
  - champs : index, profit mensuel, trésorerie mensuelle, revenus mensuels ;
  - refuser silencieusement (ou tronquer avec avertissement) au-delà de 200.
- [ ] `simulation.run_params {runId, index}` : paramètres tirés du run (clé → valeur), graine, version.
- [ ] Si le run n'a pas conservé l'échantillon (runs > 20 000 ou éviction) : erreur explicite `run_sample_unavailable`.
- [ ] Aucune donnée par run n'est envoyée sans demande explicite.
- [ ] Clic sur une trajectoire : sélection persistante dans le store (phase 08).

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

- [ ] Construire le payload depuis le résultat, le scénario et la sensibilité déjà calculée.
- [ ] Pour un point mensuel, utiliser la distribution du mois (phase 02/10).
- [ ] `contribution` réutilise `build_sensitivity` (corrélation²) ; ne pas relancer un calcul complet.
- [ ] `scenariosHash` : hash canonique du scénario (hors métadonnées volatiles) pour vérifier la cohérence.
- [ ] Ne jamais inclure : clés API, chemins locaux, nom de projet non demandé, historique de conversation.

### Lot C — Panneau UI

- [ ] Clic sur un KPI, un point du FanChart ou une barre du tornado → panneau latéral.
- [ ] Sections : définition, valeur + fourchette, entrées et contributions, sources/benchmarks, graine/version, limites.
- [ ] Bouton « Expliquer avec l'IA » :
  - désactivé si aucun fournisseur n'est configuré (avec lien vers les réglages) ;
  - affiche ce qui sera envoyé (payload) ;
  - progression/annulation ;
  - résultat avec badge « généré à partir des données ci-dessus ».
- [ ] Hors ligne : afficher l'explication déterministe (template) immédiatement.
- [ ] Accessible au clavier, fermable avec `Échap`, focus géré.

### Lot D — Explication LLM

- [ ] Handler `simulation.explain {runId, metric, point?, profileId?}` :
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
  - prompt : français, 120–220 mots, aucune recommandation d'investissement, toujours mentionner la graine et l'incertitude.
- [ ] **Validateur numérique** :
  - extraire les nombres : espaces/NBSP de milliers, virgule décimale, `%`, unités, plages `a–b` ;
  - normaliser et comparer à l'ensemble des nombres du payload (tolérance 0,1 % pour les arrondis) ;
  - autoriser les libellés `P10`, `P50`, `P90` et les unités, pas les nombres inventés ;
  - si un nombre est inconnu : réparation (max 2), sinon repli déterministe.
- [ ] Repli déterministe : phrase construite à partir du payload, sans LLM (ex. « P50 du profit : X ; P10–P90 : A–B ; graine : 42 »).
- [ ] Cache : clé `sha256(payload canonique + modèle + version du prompt)` ; LRU 100 ; TTL 24 h ; jamais de cache partagé entre projets.
- [ ] Budget : limiter les tokens, timeout 30 s, annulation.
- [ ] Journalisation : méthode, durée, statut, **jamais** le contenu du payload ni la clé.

### Lot E — Tests

- [ ] Trajectoires : count, indices, troncature, échantillon absent.
- [ ] Paramètres tirés : mêmes valeurs que celles utilisées dans le run (comparer au préfixe).
- [ ] Provenance : contributions cohérentes, hash stable, pas de secret.
- [ ] Validateur :
  - « 12 500 FCFA » accepté si 12500 est dans le payload ;
  - « 12,5 % » accepté si 0.125 est dans le payload ;
  - « 1 234 » inventé rejeté ;
  - « P10–P90 » non traité comme un nombre inventé ;
  - arrondi 12 345 → « 12 300 » accepté dans la tolérance ? (décider et tester).
- [ ] LLM : sortie valide acceptée, sortie avec nombre inventé rejetée, réparation, repli.
- [ ] Cache : hit/miss, invalidation par payload/modèle.
- [ ] Hors ligne : repli sans appel réseau.
- [ ] Vie privée : aucun secret dans le payload, les logs ou le cache disque.

## 5. Contrats

```python
def build_provenance(result: SimulationResult, metric: str, point: int | None) -> Provenance: ...
def explain(provenance: Provenance, provider, prompt_version: str) -> Explanation: ...
def validate_numbers(text: str, allowed: set[float]) -> list[str]: ...
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

- [ ] Un clic sur un KPI ouvre une provenance complète et sourcée.
- [ ] Les trajectoires ne sortent que sur demande, ≤ 200.
- [ ] L'explication LLM ne contient aucun nombre absent du payload.
- [ ] Le repli déterministe fonctionne hors ligne.
- [ ] Le cache est borné et respecte la vie privée.
- [ ] Les tests du validateur couvrent les formats français.
- [ ] Protocole `1.12.0` généré.

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

- [ ] Trajectoires, provenance et explication livrés.
- [ ] Validateur numérique testé.
- [ ] Repli hors ligne opérationnel.
- [ ] Vie privée vérifiée.
- [ ] Documentation utilisateur du panneau.
