# Politique de confidentialité — See The Future (provisoire)

> **Statut : provisoire.** Ce texte décrit le comportement réel de la version
> `3.0.0` du logiciel et doit être validé par un conseil juridique avant
> diffusion commerciale. Dernière mise à jour : 2026-11-24.

## 1. Données traitées localement

See The Future est une application de bureau **locale**. Les données suivantes
restent sur votre machine, dans le répertoire de données de l'application :

- projets, briefs, scénarios, hypothèses et événements ;
- runs de simulation persistés, versions nommées et branches ;
- préférences d'affichage, de langue et de journal d'erreurs ;
- exports `.simproj`, dossiers Markdown et PDF que vous créez.

Aucun compte, aucune synchronisation et aucun serveur See The Future ne sont
nécessaires pour utiliser l'application.

## 2. Fournisseur d'intelligence artificielle (facultatif)

L'application fonctionne sans fournisseur IA : l'explication des résultats est
alors déterministe et produite hors ligne.

Si vous configurez un fournisseur (par exemple un serveur Ollama local ou une
API distante), les données suivantes peuvent lui être envoyées pour produire
une explication :

- le brief du projet et les hypothèses nécessaires ;
- le payload de provenance minimal (chiffres, unités, graine, version moteur) ;
- votre question ou consigne d'explication.

Ne sont **jamais** envoyés : clés d'API, chemins locaux, base de données,
historique complet des runs, ni aucun autre projet.

Votre clé d'API est stockée dans le trousseau du système d'exploitation. Elle
n'est jamais écrite dans la base, les journaux, les rapports ou les fichiers
versionnés. Les appels réseau sont effectués uniquement vers le fournisseur que
vous avez choisi, depuis le composant `packages/providers`.

Le fournisseur choisi applique sa propre politique de confidentialité. Vérifiez
la destination des données avant d'activer une API distante.

## 3. Télémétrie et rapports de crash

**Aucun envoi automatique n'existe dans cette version.**

- Aucun rapport de crash n'est transmis.
- Le journal local des erreurs est **désactivé par défaut**. S'il est activé,
  il conserve au plus dix messages nettoyés sur votre machine et n'est jamais
  transmis automatiquement.
- Le bouton « Exporter le diagnostic » produit un fichier JSON local. Avant
  écriture, les clés, jetons, chemins locaux, courriels et noms de projets sont
  masqués. Vous restez libre de le relire avant de le partager avec le support.

## 4. Durée de conservation et suppression

Les données restent aussi longtemps que vous les conservez. Vous pouvez :

- supprimer un projet depuis l'application, ce qui supprime ses scénarios,
  runs, branches et versions associés ;
- supprimer les exports et sauvegardes que vous avez créés ;
- désactiver le journal d'erreurs, ce qui efface immédiatement ses entrées ;
- désinstaller l'application et supprimer son répertoire de données.

Les sauvegardes `.simproj` que vous avez copiées ailleurs restent sous votre
contrôle.

## 5. Sécurité

- Les clés sont conservées par le trousseau du système.
- Le sidecar Python communique avec le shell Tauri par un protocole JSON-RPC
  local, sans écoute réseau.
- Les scripts générés ne sont jamais exécutés sans revue humaine et sans
  sandbox.
- Les exports de dossier ne contiennent ni clé, ni chemin local, ni donnée
  personnelle.

## 6. Vos droits

Selon votre juridiction, vous pouvez disposer de droits d'accès, de
rectification, d'effacement et de portabilité. Comme les données restent sur
votre machine, vous exercez ces droits directement en consultant, modifiant ou
supprimant vos fichiers et projets.

## 7. Contact

Voir la fiche du projet et l'écran « À propos ». Un canal de support officiel
sera publié avec la version `3.0.0`.
