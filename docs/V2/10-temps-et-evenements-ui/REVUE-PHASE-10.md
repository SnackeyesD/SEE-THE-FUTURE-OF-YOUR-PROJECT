# Revue de la phase 10 — temps & événements UI

## 1. Objet et périmètre

Revue du dépôt `SEE-THE-FUTURE-OF-YOUR-PROJECT`, branche `v3/cockpit`, à partir du commit `d09ab21` et des modifications non commitées correspondant à la phase 10.

La revue comprend :

- l'inspection statique du protocole, du moteur, du sidecar et des composants React ;
- l'exécution des principaux contrôles de la CI ;
- une revue indépendante ciblée sur les changements UI ;
- l'analyse de la proposition détaillée de livraison de la phase 10.

Aucun test utilisateur ni contrôle visuel automatisé de l'application n'a été réalisé. Les constats UI ci-dessous sont donc des constats de revue de code, pas tous des bugs reproduits dans la Webview.

## 2. Synthèse

Le socle est bien structuré : application desktop local-first, React/TypeScript, Tauri/Rust et Python, avec une séparation claire entre moteur de calcul, sidecar, protocole et interface.

La phase 10 est déjà largement amorcée dans le working tree : histogrammes mensuels du calcul final, catalogue généré, curseur de temps, inspecteur mensuel, frise d'événements, éditeur, palette et persistance du scénario.

**Verdict : bon socle technique, mais phase 10 encore WIP. Ne pas merger en l'état.** Les contrôles existants sont majoritairement verts, mais plusieurs bugs fonctionnels et l'absence de nouveaux tests UI empêchent de considérer la phase comme terminée.

## 3. Contrôles exécutés

| Contrôle | Résultat |
|---|---|
| `protocol:check` | Vert, fichiers générés à jour |
| `catalog:check` | Vert, catalogue à jour |
| TypeScript strict | Vert |
| Lint et `ui:check` | Verts |
| Build web de production | Vert |
| Tests desktop Vitest | **107/107**, 17 fichiers |
| Tests du protocole | **3/3** |
| Moteur Python | **130/130**, Ruff vert |
| Storage | **61/61**, Ruff vert |
| Providers | **18/18**, Ruff vert |
| Agent core | **48/48**, Ruff vert |
| Benchmarks | **8/8**, Ruff vert |
| Sandbox | **28/28**, Ruff vert |
| Rust, exécution séquentielle | **9/9** |
| `git diff --check` | Propre |

### Instabilité du harnais sidecar

Deux exécutions standard de `npm run sidecar:test` ont produit respectivement **46/48** puis **45/48**, avec des erreurs `_queue.Empty` après le timeout de lecture de 5 secondes. Les tests en échec variaient d'une exécution à l'autre et passaient lorsqu'ils étaient relancés isolément.

Un diagnostic sans modification du dépôt, avec le délai de lecture porté à 30 secondes, a donné **48/48**.

**Action recommandée :** augmenter le timeout du harnais pour les opérations lentes ou le démarrage à froid, et afficher `stderr` ainsi que l'état du processus lorsqu'un timeout se produit. La validation standard actuelle n'est pas fiable sur la machine utilisée pour la revue.

## 4. Constats de revue

### Sévérité élevée

| Fichier | Constat | Conséquence |
|---|---|---|
| `apps/desktop/src/components/cockpit/KpiBar.tsx:60-71` | Le mois n'est pris en compte que s'il appartient aux options `[6, 12, 18, horizon]`. | Au mois 7, le graphique et l'inspecteur affichent le mois 7, mais la probabilité de point mort reste celle de l'horizon. |
| `apps/desktop/src/screens/CockpitScreen.tsx:222-229,462-477` | Une modification effectuée pendant l'enregistrement peut être suivie d'un `setDirty(false)` au retour de l'ancien IPC. | Le badge et la garde de navigation peuvent considérer à tort les nouvelles modifications comme sauvegardées. |
| `apps/desktop/src/App.tsx:257-280,812-813` | « Recharger l'application » appelle `bootstrap()` et change la vue sans passer par la garde de `navigate()`. | Les changements locaux du cockpit peuvent être perdus sans confirmation. |

### Sévérité moyenne

| Fichier | Constat | Conséquence |
|---|---|---|
| `apps/desktop/src/screens/CockpitScreen.tsx:435-449,868-875` | L'éditeur se ferme immédiatement après le lancement fire-and-forget du calcul. | Un refus du sidecar n'est plus affiché dans le formulaire et l'utilisateur ne peut pas corriger directement sa saisie. |
| `apps/desktop/src/hooks/useCockpitHotkeys.ts:38-53` | `Ctrl/Cmd+K` et `Ctrl/Cmd+S` sont traités avant la garde des cibles interactives. | La palette peut voler le focus pendant la saisie. |
| `apps/desktop/src/lib/keyboard.ts:9-17` et `useCockpitHotkeys.ts:53-61` | Les boutons ne sont pas considérés comme interactifs pour la touche Espace. | Espace sur « Enregistrer », « Commandes » ou un jalon lance la lecture au lieu d'activer le bouton. |
| `apps/desktop/src/hooks/useUndoRedoHotkeys.ts:13-23` | Undo/redo ne vérifie pas `isInsideModal`. | `Ctrl+Z` peut modifier le scénario derrière un dialogue et démonter l'événement en cours d'édition. |
| `apps/desktop/src/styles.css:1406-1413,1530-1543` | La frise impose `overflow:hidden`, tandis que le menu s'ouvre sous un bloc de 28 px. | Le menu contextuel est presque entièrement clippé sur une seule ligne et sur la dernière ligne. |
| `apps/desktop/src/components/cockpit/EventTimeline.tsx:144-155,277-309` | `pointercancel` appelle le même gestionnaire qu'un drop réussi. | Une annulation tactile peut valider le déplacement et lancer un calcul. |

### Sévérité faible

- `apps/desktop/src/hooks/useDialogFocus.ts:14-42` : le focus n'est pas restitué à l'élément déclencheur après fermeture d'un dialogue.
- `apps/desktop/src/screens/CockpitScreen.tsx:213-220` : le bornage du mois après réduction de l'horizon est silencieux, alors que la phase 10 demande un signalement explicite.

## 5. Lacune de tests

Aucun nouveau fichier `*.test.ts[x]` n'est ajouté sous `apps/desktop/src` pour la phase 10. Les fichiers existants adaptent surtout les harnais et assertions précédents.

Les tests à ajouter en priorité sont :

1. probabilité de point mort pour un mois arbitraire ;
2. changement de mois sans nouvel appel IPC ;
3. modification du scénario pendant une sauvegarde et rechargement avec changements en attente ;
4. raccourcis dans les champs, sur les boutons et derrière les dialogues ;
5. géométrie de la frise, drop unique, `pointercancel` et menu contextuel ;
6. conservation de l'éditeur et de sa saisie après une erreur IPC ;
7. ajout/modification/suppression d'événement avec undo/redo ;
8. playback, pause sur perte de focus et fin d'horizon ;
9. restauration du focus et bornage signalé du mois.

## 6. Analyse de la proposition de phase 10

### Avis général

La proposition est **cohérente avec l'architecture et recevable après amendements**. Elle ne part pas de zéro : une grande partie des lots est déjà présente dans le working tree. Elle doit maintenant servir de plan de finition et de durcissement, pas seulement de plan d'implémentation.

| Lot | État constaté | Travail restant |
|---|---|---|
| Lot 0 — protocole et moteur | Présent ; tests moteur et sidecar ciblés verts | Mettre à jour la cartographie documentaire `1.11 → 1.12 → 1.13` et fiabiliser le harnais sidecar |
| Lot 0 bis — catalogue | Génération présente et `catalog:check` vert localement | Ajouter le check à la CI et les tests de parité des types et de validité des magnitudes |
| Lot 0 ter — socle | `events`/`seasonality` préservés et provider stabilisé par `project.id` | Corriger `KpiBar`, centraliser ou compléter le bornage de `selection`, couvrir boutons/dialogues dans les gardes clavier |
| Lots B à E — temps, frise, éditeur, palette | Composants présents | Corriger les bugs de la section 4 et ajouter les tests prévus ; confirmer la mémoïsation et les tests de rendu |
| Lot F — persistance | Bouton, callback, badge et garde de navigation présents | Corriger la course de sauvegarde et le contournement par rechargement |
| Documentation | À faire | README de phase, plan V3, ADR 0017 et README principal encore annoncé en phase 07 |

### Amendements nécessaires à la proposition

1. **Sauvegarde asynchrone :** après `await onSaveScenario(...)`, recalculer `dirty` en comparant l'instantané sauvegardé avec le scénario alors présent dans le store ; ne jamais forcer `false` sans cette comparaison.
2. **Rechargement :** appliquer la même confirmation que pour une navigation sortante avant de remplacer les données du cockpit.
3. **Erreur de l'éditeur :** exposer un résultat awaitable du démarrage du run, ou un mécanisme équivalent, afin de fermer l'éditeur seulement après acceptation du sidecar et de conserver le brouillon en cas de refus.
4. **Clavier :** couvrir explicitement les boutons et liens pour Espace, déplacer les gardes avant les raccourcis à modificateurs et suspendre undo/redo dans les dialogues.
5. **Frise :** séparer l'annulation de pointeur du drop et rendre le menu hors du conteneur clippé, par exemple via un portal ou une couche non clippée.
6. **Harnais sidecar :** intégrer la correction du timeout et le diagnostic de `stderr` aux critères de validation.
7. **CI et documentation :** ajouter `catalog:check` aux jobs concernés et aligner les versions de protocole dans le plan V3 et les ADR.

### Incohérence à lever : graine et état « dirty »

La proposition demande de comparer `session.scenario` **et `session.seed`** pour le badge de modifications, tout en précisant que la graine n'appartient pas au scénario persisté. Ces deux règles sont incompatibles : changer la graine rendrait le scénario « dirty » sans que « Enregistrer le scénario » puisse nécessairement résoudre cet état.

**Recommandation pour la phase 10 :** conserver le dirty sur le scénario seul, tant que la graine reste attachée au run. Si la graine doit être persistée avec le scénario, ajouter explicitement cette évolution au contrat et aux tests.

## 7. Réponse aux deux demandes d'accord explicite

### (a) `includeMonthlyHistograms: true` dans le parcours Résultats

**Avis favorable.**

Cela garantit que le run final rechargé par le cockpit contient déjà les distributions de tous les mois, sans recalcul à l'ouverture et sans fabrication de données dans React. Le surcoût de persistance est acceptable sous les conditions déjà prévues :

- histogrammes dans les runs finaux uniquement ;
- partiels sans histogrammes mensuels ;
- payload borné et testé sous 200 Ko ;
- message explicite et action de relance pour les anciens runs sans distributions.

### (b) Nouveau `ScenarioRecord` à chaque sauvegarde, sans upsert en phase 10

**Avis favorable comme limitation temporaire et documentée.**

Le comportement correspond bien à l'implémentation actuelle de `project_service.save_scenario`, qui appelle systématiquement `store.scenarios.add(...)`. Ne pas introduire d'upsert dans cette phase limite le risque de migration ou de régression de persistance.

Conditions :

- conserver la clé du provider sur `project.id` pour ne pas perdre l'historique des runs à la sauvegarde ;
- garder déterministe le choix du scénario actif après rechargement ;
- tester explicitement le comportement de deux sauvegardes successives ;
- inscrire l'upsert, la déduplication ou le modèle branches/versions comme dette de la phase 13.

## 8. Ordre recommandé avant livraison

1. Corriger les trois problèmes de sévérité élevée et ajouter leurs tests de régression.
2. Corriger les gardes clavier, l'éditeur et la frise, avec les tests UI prévus par la proposition.
3. Fiabiliser `sidecar:test` et ajouter `catalog:check` à la CI.
4. Mettre à jour la documentation et l'ADR 0017.
5. Rejouer toutes les validations sur un working tree propre.
6. Découper ensuite les changements en commits cohérents et vérifiables ; le working tree actuel mélange déjà plusieurs lots, donc chaque commit intermédiaire doit rester compilable et testable.

## 9. Conclusion

La direction proposée est la bonne : protocole `1.11.0`, histogrammes du final, catalogue généré, raccourcis `1–8` et persistance explicite du scénario sont des choix cohérents. La phase ne doit cependant pas être validée sur la seule base des tests actuels : les bugs de mois sélectionné et de persistance, ainsi que les lacunes de tests UI, doivent être traités avant le merge.
