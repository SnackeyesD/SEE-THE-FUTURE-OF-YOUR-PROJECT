# ADR 0001 — Coquille desktop : Tauri 2

- **Statut** : accepté
- **Date** : 2026-11-07
- **Contexte** : phase 01

## Décision

Utiliser **Tauri 2** comme coquille desktop, avec une UI React/TypeScript et un sidecar Python.

## Contexte et raisons

- Installateur et consommation mémoire plus faibles qu'Electron : important pour des PC modestes et des connexions limitées.
- Accès natif au trousseau OS, aux fichiers et aux mises à jour signées.
- Support des sidecars (binaires externes) pour embarquer le moteur Python.
- La cible prioritaire est Windows, puis Linux, puis macOS.

## Alternatives

- **Electron** : écosystème plus large et shell 100 % TypeScript, mais installateur et RAM plus lourds.
- **Application web auto-hébergée seule** : ne répond pas au local-first ni à l'usage hors ligne.

## Conséquences

- Une partie du shell est en Rust (fenêtre, cycle de vie, trousseau, supervision du sidecar).
- L'équipe doit maîtriser les bases de Rust et la signature de code.
- Electron reste une porte de sortie si l'équipe refuse Rust, au prix d'un produit plus lourd.

## Gestionnaire de paquets JavaScript

**npm workspaces** est retenu (au lieu de pnpm) pour éviter une installation globale supplémentaire tout en conservant un monorepo fonctionnel. Le choix pourra être revu sans impact architectural.
