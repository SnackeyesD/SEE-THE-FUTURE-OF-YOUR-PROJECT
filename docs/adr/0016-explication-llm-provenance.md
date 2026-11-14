# ADR 0016 — Provenance et explication LLM vérifiée

- **Statut** : accepté
- **Date** : 2026-11-14
- **Contexte** : phase 01, s'applique en phase 12

## Décision

L'explication d'un chiffre est **ancrée sur un payload de provenance** et vérifiée avant affichage. Le LLM ne calcule jamais.

### Payload de provenance

Pour une métrique agrégée ou un point mensuel :

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

- Construit par le sidecar à partir du résultat, du scénario et de la sensibilité déjà calculée.
- `contribution` réutilise `build_sensitivity` (corrélation²), sans relancer de simulation.
- `scenariosHash` : hash canonique du scénario (hors champs volatils) pour vérifier la cohérence.
- **Jamais** inclus : clés API, chemins locaux, historique de conversation, projet entier, secrets.

### Explication

- Sortie structurée :
  ```json
  {
    "summary": "string",
    "points": [{ "text": "string", "references": ["p50", "seed"] }],
    "caveats": ["string"]
  }
  ```
- Prompt en français, 120–220 mots, aucune recommandation d'investissement, mention obligatoire de la graine et de l'incertitude.
- Le LLM reçoit **uniquement** le payload de provenance sérialisé.
- Le mode hors ligne ou sans fournisseur produit une **explication déterministe** immédiate, construite à partir du payload.

### Validateur numérique

- Extraire les nombres du texte : espaces et NBSP de milliers, virgule décimale, `%`, unités, plages `a–b`.
- Normaliser puis comparer à l'ensemble des nombres du payload avec une tolérance d'arrondi **relative de 0,1 %** (et une tolérance absolue pour les petits nombres, documentée).
- Autoriser explicitement les libellés `P10`, `P50`, `P90`, les unités et les bornes de plage, qui ne sont pas des nombres inventés.
- Un nombre inconnu déclenche une **réparation** (maximum 2 tentatives) ; en cas d'échec, repli déterministe.
- Le validateur s'exécute **côté sidecar**, pas seulement côté client. Le client peut garder une vérification d'affichage, mais elle n'est pas la garantie.

### Cache et vie privée

- Clé : `sha256(payload canonique + modèle + version du prompt)`.
- LRU 100 entrées, TTL 24 h, jamais partagé entre projets.
- Aucune clé, aucun chemin, aucun contenu non nécessaire dans le cache.
- Journalisation : méthode, durée, statut, **jamais** le payload ni la clé.
- Timeout 30 s, budget de tokens, annulation.
- L'explication est **opt-in** : bouton explicite, aperçu de ce qui sera envoyé.

## Contexte et raisons

- La spec affirme « aucun nombre absent du payload », mais un simple regex ne suffit pas : la v2 utilise `apps/desktop/src/lib/narration.ts`, qui gère mal les milliers, les pourcentages, les plages et les arrondis, et s'exécute côté client uniquement.
- Un chiffre inventé détruit la confiance plus vite qu'une absence d'explication.
- Le mode hors ligne est un principe produit : l'explication doit rester disponible sans fournisseur.
- La provenance est aussi utile sans LLM (panneau « d'où vient ce chiffre ? »).

## Alternatives

- **Faire confiance au prompt** : insuffisant ; un modèle peut inventer un nombre plausible.
- **Interdire tous les nombres dans l'explication** : rend le texte inutile.
- **Validation par un second LLM** : coût, latence, non déterministe.
- **Envoyer tout le projet au LLM** : fuite de données et coût inutile.

## Conséquences

- La phase 12 doit livrer un validateur testé sur les formats français : `12 500`, `12,5 %`, `1 234–5 678`, `P10–P90`.
- Une explication sans fournisseur n'est jamais une erreur : c'est le repli normal.
- Le panneau de provenance est accessible au clavier et fermable avec `Échap`.
- Les trajectoires ne sortent que sur demande explicite, ≤ 200 runs, avec une erreur claire si l'échantillon n'est plus disponible.
- Toute explication affichée porte un badge « généré à partir des données ci-dessus ».

## Vérification

- « 12 500 FCFA » accepté si 12500 est dans le payload.
- « 12,5 % » accepté si 0.125 est dans le payload.
- « 1 234 » inventé rejeté.
- « P10–P90 » non traité comme un nombre inventé.
- Une sortie avec un nombre inventé est réparée ou remplacée par le repli.
- Test hors ligne : aucune requête réseau, repli immédiat.
- Test de vie privée : aucun secret dans le payload, les logs ou le cache disque.
