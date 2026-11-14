# Phase 10 — Temps & événements UI

> **Objectif** : piloter la simulation dans le temps et dans les imprévus : curseur de mois, distribution de l'état au mois choisi, frise d'événements éditable, catalogue, raccourcis et palette de commandes.

**Références** : `V3-COCKPIT.md` §6.1, §7 (I4, I5, I13), §3.3.
**Dépend de** : phase 09 (cockpit), phase 05 (moteur d'événements), phase 08 (commandes).
**Débloque** : 11 (objectif avec événements), 15 (démo).
**Profil** : intermédiaire UI (senior pour la frise et l'accessibilité) ; 5–6 jours.

---

## 1. Contexte

Le cockpit statique montre l'horizon complet. La V3 doit permettre de :

- lire l'état **mois par mois** (distribution, pas seulement une moyenne) ;
- ajouter un imprévu, le placer, régler sa durée et son intensité, et voir l'effet ;
- tout faire au clavier, sans dépendre du glisser-déposer.

## 2. Périmètre

**Inclus**

- Curseur de temps, lecture/pause, raccourcis.
- Histogramme de l'état au mois sélectionné (profit/trésorerie).
- Frise d'événements : ajout, déplacement, redimensionnement, suppression, activation.
- Catalogue d'événements issu du moteur, éditeur d'intensité et de probabilité.
- Palette de commandes (Ctrl+K).
- Accessibilité et alternatives clavier à la frise.
- Tests de géométrie, de commandes et d'intégration.

**Exclu**

- Recherche d'objectif (phase 11).
- Heatmap/tornado (phase 11).
- 3D (phase 14).

## 3. Livrables

- [ ] `components/cockpit/TimeScrubber.tsx`, `MonthInspector.tsx`.
- [ ] `components/cockpit/EventTimeline.tsx`, `EventCatalog.tsx`, `EventEditor.tsx`.
- [ ] `components/CommandPalette.tsx`.
- [ ] Schéma de distributions mensuelles côté moteur/protocole (extension de la phase 02 si absente).
- [ ] Raccourcis documentés dans l'aide.
- [ ] Tests et captures.

## 4. Tâches détaillées

### Lot A — Distribution mensuelle

- [ ] Vérifier que le payload final fournit, par mois, un histogramme (ou des quantiles suffisants) pour profit et trésorerie.
- [ ] Si la phase 02 n'a livré que P10/P50/P90 : ajouter `MonthlyHistogram` (20–30 bins) au **final uniquement**.
  - Taille estimée : 36 mois × 2 métriques × 25 bins × 3 nombres ≈ 60 Ko.
  - Ne pas envoyer les histogrammes dans les partiels (trop lourd) ; les partiels gardent les bandes.
- [ ] L'UI affiche « distribution du dernier calcul final » avec la date/graine, pas une distribution inventée.

### Lot B — Curseur de temps

- [ ] `TimeScrubber` : piste de 1 à horizon, poignée, ticks trimestriels.
- [ ] Lecture/pause : `Espace`, vitesse lente (1 mois/400 ms) ; pause automatique quand la fenêtre perd le focus.
- [ ] Flèches ←/→ : mois précédent/suivant ; `Home`/`End` : premier/dernier.
- [ ] Le mois sélectionné met à jour :
  - le crosshair du FanChart ;
  - l'histogramme du `MonthInspector` ;
  - la probabilité cumulée de point mort à ce mois.
- [ ] **Aucun recalcul moteur** pour changer de mois : tout vient du résultat courant.
- [ ] Si le mois dépasse l'horizon du résultat (changement de scénario), clamper et signaler.

### Lot C — Frise d'événements

- [ ] Représenter chaque événement comme un bloc `[start, start + duration)` sur la frise.
- [ ] Glisser le bloc : déplacement d'un mois entier, snap visuel.
- [ ] Poignées gauche/droite : durée minimale 1 mois, ne pas dépasser l'horizon.
- [ ] Pendant le drag : mise à jour **locale** de la position (pas de simulation) ; au drop : commande + `draft`/`final`.
- [ ] Double-clic : ouvre `EventEditor`.
- [ ] Menu contextuel : activer/désactiver, dupliquer, supprimer (annulable).
- [ ] Couleur par type, mais aussi libellé/icône (pas de couleur seule).
- [ ] **Alternative clavier** : sélection du bloc, flèches pour déplacer, `Shift+←/→` pour la durée, `Suppr`, `Entrée` pour éditer.
- [ ] Empilement vertical si les événements se chevauchent.

### Lot D — Catalogue et éditeur

- [ ] Catalogue depuis le moteur (types, libellés, cibles, magnitudes par défaut) ; pas de duplication en dur.
- [ ] Ajout : place l'événement au mois sélectionné, durée par défaut 3 mois, probabilité 100 %, magnitude par défaut.
- [ ] `EventEditor` :
  - type (lecture seule après création ou changement explicite) ;
  - début et durée (champs numériques) ;
  - probabilité 0–100 % ;
  - intensité : selon la loi (min/mode/max ou moyenne/écart-type), aperçu ;
  - cible et mode affichés en clair ;
  - activé/désactivé ;
  - avertissement si la fenêtre dépasse l'horizon ;
  - erreurs de validation renvoyées par le sidecar affichées telles quelles.
- [ ] L'aperçu d'intensité est un **paramètre**, pas un résultat de simulation.
- [ ] Chaque modification passe par une commande (undo).

### Lot E — Palette et raccourcis

- [ ] `Ctrl+K` / `Cmd+K` : palette avec recherche d'actions (ajouter un événement, épingler, relancer, changer de disposition, aller au mois, ouvrir l'aide).
- [ ] Raccourcis : `Espace` lecture, `←/→` temps, `F` plein écran, `1–6` vues, `Ctrl+Z/Y`, `Échap` ferme les dialogues.
- [ ] Ne pas intercepter les raccourcis quand un champ de saisie a le focus.
- [ ] Aide contextuelle (`?`) listant les raccourcis.

### Lot F — Tests

- [ ] Géométrie : mois ↔ pixel, clamp, drag au-delà des bornes.
- [ ] Clavier : déplacement, durée, suppression, annulation.
- [ ] Éditeur : validation, erreur serveur, annulation.
- [ ] Intégration : ajouter un événement → partiel → final ; l'effet est visible ; undo restaure.
- [ ] Distribution mensuelle : sélection d'un mois met à jour l'histogramme sans nouvel appel IPC.
- [ ] Accessibilité : rôles, focus, alternatives.

## 5. Contrats

```ts
type EventDraft = {
  id: string;
  type: EventType;
  startMonth: number;   // 1-based
  durationMonths: number;
  probability: number;
  magnitude: DistributionSpec;
  enabled: boolean;
};

type MonthDistribution = {
  month: number;
  profit: Histogram;
  cash: Histogram;
};
```

Invariants :

- La frise ne dépasse jamais l'horizon.
- Un événement désactivé reste visible mais grisé et n'est pas envoyé au moteur (ou envoyé `enabled:false`, au choix — le moteur l'ignore).
- Le mois sélectionné est indépendant du run ; il survit à un nouveau résultat si l'horizon le permet.
- Un drag ne déclenche pas plus d'un calcul par drop.

## 6. Pièges

- **Recalculer à chaque pixel de drag** : le drop seul déclenche.
- **Distribution mensuelle calculée dans l'UI** : interdite ; elle vient du moteur.
- **Histogrammes dans les partiels** : trop lourds ; final seulement.
- **Confondre mois 1-based et 0-based** : l'API est 1-based, l'interne 0-based.
- **Palette qui capture les flèches** : vérifier `event.target` (input, textarea, contenteditable).
- **Couleur seule** : toujours un libellé/icône.
- **Playback qui continue en arrière-plan** : pause sur `blur` et `visibilitychange`.

## 7. Critères d'acceptation

- [ ] Le curseur de temps change l'état affiché sans recalcul.
- [ ] L'histogramme du mois sélectionné est fourni par le moteur.
- [ ] Un événement peut être ajouté, déplacé, redimensionné, édité, désactivé, supprimé, annulé.
- [ ] L'effet d'un événement est visible sur le graphique après le calcul.
- [ ] Tout est faisable au clavier.
- [ ] Les raccourcis n'interfèrent pas avec la saisie.
- [ ] Tests et `ui:check` verts.

## 8. Performance

- Changer de mois < 16 ms.
- Drag de frise : 60 i/s en local, un seul calcul au drop.
- Payload final avec histogrammes : < 200 Ko.
- Partiels inchangés : < 50 Ko.

## 9. Risques

| Risque | Mitigation |
|---|---|
| Frise complexe/inaccessible | Alternative clavier, tests, drag simple |
| Payload trop gros | Histogrammes final seulement, bins limités |
| Événements incohérents | Validation moteur, messages clairs |
| Recalculs excessifs | Drag local, drop unique |
| Raccourcis conflictuels | Guard input, documentation |

## 10. Definition of Done

- [ ] Temps, événements et palette livrés.
- [ ] Distribution mensuelle fournie par le moteur.
- [ ] Accessibilité clavier validée.
- [ ] Tests d'intégration draft/final verts.
- [ ] Documentation des raccourcis et du catalogue.
