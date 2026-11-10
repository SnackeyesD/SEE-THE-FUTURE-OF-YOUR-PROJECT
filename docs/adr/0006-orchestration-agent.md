# ADR 0006 — Orchestration de l'agent, permissions et anti-injection

## Statut

Accepté — phase 05.

## Contexte

Le produit doit transformer un dialogue en brief structuré, puis en simulations
reproductibles, sans laisser le modèle inventer de chiffres ni contourner les
permissions. Le même socle doit rester utilisable avec un modèle local et ne
jamais recevoir de clé API en base ou dans les traces.

## Décision

### Séparation des responsabilités

- `packages/agent-core` ne fait aucune E/S réseau, trousseau ou base de données.
  Il dépend uniquement de `see-engine`, `see-providers` et Pydantic.
- Le sidecar fournit les fonctions d'E/S : chargement du brief, persistance des
  scénarios et runs, journal de permissions, trace et sessions.
- Le shell Rust résout le profil fournisseur via `agent.prepare`, lit la clé
  dans le trousseau et l'injecte uniquement pour `agent.turn`. L'UI ne peut pas
  appeler directement `agent.turn` ni `agent.prepare` via `agent_call`.
- Toute génération passe par `packages/providers`.

### Rôles et machine à états

- Rôles : `interviewer`, `modeler`, `narrator`, `delegate`, `coder`.
- Le rôle est déduit de l'état du parcours, avec un rôle explicite possible.
- Les transitions sont déclarées dans `state_machine.py` et calculées par plus
  court chemin. Une transition interdite échoue explicitement.
- Les prompts système sont versionnés (`PROMPT_VERSION`) et le système est
  reconstruit à chaque tour ; il n'est pas stocké dans le fil persistant.
- Le fil persistant ne contient que les messages utilisateur, assistant et
  outils, normalisés avant stockage.

### Outils et sorties

- Chaque outil a un modèle Pydantic d'entrée, un modèle de sortie optionnel,
  une description courte et une politique de permission par défaut.
- Une entrée invalide est refusée avant exécution avec une erreur typée.
- Les chiffres de simulation ne proviennent que du moteur ; les outils de
  simulation appellent `see-engine` et renvoient un résultat sérialisé.
- Les sorties LLM structurées sont validées par schéma. La boucle de réparation
  est bornée à deux essais, puis échoue explicitement.
- `run_custom_script` ne s'exécute jamais en phase 05 : il retourne une demande
  de revue humaine (`requiresReview`). La sandbox arrive en phase 07.

### Permissions

- Décisions : `allow`, `ask`, `deny`.
- Valeurs par défaut : brief, hypothèses, simulation, comparaison et benchmark
  sont autorisés ; recherche web, export et script demandent une autorisation.
- `run_custom_script` demande toujours, même si un override `allow` existe.
  Un override `deny` gagne toujours.
- La politique est appliquée dans l'agent, jamais uniquement dans l'UI.
- Les décisions utilisateur et agent sont journalisées dans
  `permission_events` (outil, portée, décision, acteur, date).
- Une demande de permission suspend le tour avec les appels d'outils en attente.
  La reprise exige une approbation par identifiant d'appel ou nom d'outil.

### Anti-injection et secrets

- Les contenus externes (recherche web, documents) sont des données non
  fiables : ils sont délimités et ne sont jamais traités comme instructions.
- Les motifs d'injection connus sont détectés et bloqués avant transmission.
- Les traces retirent les secrets et remplacent les contenus sensibles par leur
  taille. Les prompts sont référencés par empreinte SHA-256, pas en clair.
- Aucune clé API n'est stockée dans les sessions, traces, événements ou logs.

### Persistance et protocole

- Migration storage v3 : `agent_sessions`, `agent_trace`, `permission_events`.
- Les sessions, traces et événements de permission sont inclus dans la copie,
  l'export `.simproj` et l'import. Les identifiants de session sont remappés.
- Le protocole passe en `1.4.0` (puis `1.5.0` en phase 06 pour les méthodes
  `project.*`) avec les méthodes `agent.state`, `agent.start`,
  `agent.reset`, `agent.permission.*`, `agent.trace`, `agent.trace.export`,
  `agent.tools` et les commandes Rust `agent_turn` / `agent_call`.
- `agent_call` applique une liste blanche de méthodes ; `agent_turn` et
  `agent.prepare` restent réservés au shell pour préserver l'injection de clé.

### Traçabilité

- Chaque tour journalise requête, réponse, outils, permissions, erreurs, tokens,
  coût et latence.
- La trace est exportable en JSON depuis le stockage du projet.
- Le contenu des prompts et réponses n'est pas conservé par défaut.

## Conséquences

- L'UI de phase 06 consomme les contrats `agent.*` sans accéder aux secrets.
- Le client MCP reste optionnel et désactivé par défaut.
- Les clients réels de recherche web, benchmarks et export de rapport restent
  injectables ; leurs contenus et implémentations arrivent aux phases 08/09.
- L'annulation utilisateur et le basculement de rôle en cours de tour restent à
  traiter dans les phases suivantes.
- Toute évolution des outils doit être ajoutée au schéma de protocole et au
  registre, avec des tests de permission et d'injection.
