# ADR 0002 — Transport IPC : JSON-RPC 2.0 sur stdio (NDJSON)

- **Statut** : accepté
- **Date** : 2026-11-07
- **Contexte** : phase 01

## Décision

Le shell Rust et le sidecar Python communiquent en **JSON-RPC 2.0**, encodé en **NDJSON** (un objet JSON par ligne) sur l'entrée/sortie standard du processus sidecar.

## Contexte et raisons

- Aucun port réseau ouvert, donc aucune surface d'attaque supplémentaire.
- Le cycle de vie du sidecar est lié au processus parent.
- Débogage simple : les messages sont lisibles ligne par ligne.
- Les événements de streaming (tokens, progression) sont des notifications JSON-RPC sans `id`.
- Une limite de taille par message (1 Mio) protège contre les entrées abusives.

## Alternatives

- **HTTP sur `127.0.0.1` + jeton** : utile si des flux complexes ou plusieurs clients l'exigent ; à réserver à un besoin réel.
- **gRPC** : plus lourd, surdimensionné pour ce socle.

## Conséquences

- Les réponses volumineuses doivent être découpées ou écrites dans des fichiers/artéfacts séparés.
- Le protocole doit rester strictement versionné (`packages/protocol`).
- Le sidecar ne doit jamais écrire autre chose que du JSON sur stdout ; les logs vont sur stderr.
