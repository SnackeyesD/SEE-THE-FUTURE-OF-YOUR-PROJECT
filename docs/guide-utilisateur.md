# Guide utilisateur — See The Future

> Version `3.0.0` (provisoire). Deux pages suffisent pour un premier résultat.

## 1. Installer et démarrer

1. Lancez l'installateur Windows (ou l'AppImage Linux) de la version `3.0.0`.
2. Ouvrez See The Future. L'application démarre son moteur local ; aucun compte
   n'est demandé.
3. Si le bandeau indique « Sidecar arrêté », ouvrez **Réglages** et cliquez sur
   **Redémarrer**. Le diagnostic local peut aider le support.

L'application fonctionne sans réseau. Un fournisseur d'IA n'est nécessaire que
pour l'explication en langage naturel.

## 2. Obtenir un premier résultat en moins de deux minutes

1. **Projets** → carte **Partir d'un projet d'exemple** →
   `retail-depot-brazzaville`.
2. Suivez le parcours guidé, ou ignorez-le : il ne bloque aucune action.
3. Ouvrez **Hypothèses** et vérifiez les valeurs marquées « estimation ».
4. Ouvrez **Simulation**, laissez la qualité **finale** (5 000 runs) et lancez
   le calcul. Un run final est conservé ; un brouillon ne l'est jamais.
5. Ouvrez **Résultats** : P10/P50/P90, probabilité de perte, point mort et
   sensibilité viennent du moteur, jamais du texte.

## 3. Comprendre les chiffres

- **P10–P90** : 80 % des tirages sont dans cette fourchette ; ce n'est pas une
  garantie.
- **Probabilité de perte** : part des runs où le profit cumulé est négatif.
- **Sensibilité** : une contribution élevée indique une hypothèse qui déplace
  le résultat, pas une hypothèse certaine.
- **Graine et version moteur** : deux runs ne se comparent que si ces deux
  valeurs sont identiques.

Le panneau **« D'où vient ce chiffre ? »** montre la provenance et les bornes.
Une valeur absente s'affiche « non disponible », jamais `0`.

## 4. Explorer sans casser la référence

- **Cockpit** : modifiez les hypothèses au curseur ; les drafts sont réactifs,
  le bouton **Calculer en final** fige un run comparable.
- **Événements** : activez un choc, choisissez le mois de début et la durée.
  Un événement désactivé ne consomme aucun tirage.
- **Branches** : dupliquez un scénario pour tester une variante. Les résultats
  ne sont pas annulables ; *undo* restaure les entrées et invalide le run.
- **Versions** : nommez un état pour le retrouver, puis restaurez-le sans
  supprimer l'historique.

## 5. Exporter un dossier

Dans **Résultats** :

- **Exporter le dossier** produit un Markdown ;
- **Exporter en PDF** produit le même contenu, paginé, hors ligne.

Le dossier contient les hypothèses, les résultats, les branches, la
méthodologie, la traçabilité et l'avertissement de transparence. Il ne contient
ni clé, ni chemin local, ni donnée personnelle.

## 6. Fournisseur d'IA (facultatif)

1. **Réglages** → **Fournisseurs** → ajoutez un profil.
2. La clé est stockée dans le trousseau du système, jamais dans la base.
3. Choisissez le rôle et testez la connexion.
4. L'explication générée est vérifiée numériquement. En cas d'échec, un repli
   déterministe est affiché.

Sans fournisseur, tout le reste fonctionne : brief, simulation, résultats,
exports et explication déterministe.

## 7. Données, diagnostic et support

- Les projets, runs et versions restent sur votre machine.
- **Réglages** → **Exporter le diagnostic** produit un JSON local nettoyé
  (clés, chemins, courriels et noms de projets masqués).
- Le **journal local des erreurs** est désactivé par défaut. S'il est activé,
  il reste local et limité à dix entrées.
- Aucun envoi automatique n'existe dans cette version.

## 8. En cas de problème

| Symptôme | Action |
|---|---|
| Sidecar arrêté | Réglages → Redémarrer, puis exporter le diagnostic |
| Résultat absent | Vérifier qu'un run **final** terminé existe |
| Export refusé | Le run doit être final, terminé et avoir un résultat détaillé |
| Chiffres différents | Vérifier graine et version moteur avant de comparer |
| Fournisseur en échec | Tester la connexion, vérifier la clé dans le trousseau |

Les limites connues et les nouveautés sont listées dans `CHANGELOG.md`.
