# Audit design — See The Future (phase 01)

> Rapport de référence de la refonte. Chaque problème a un **ID** (ex. `P1-03`) réutilisable par les phases suivantes. Captures : `captures/` (1440×960 et 480×900, Chromium, mode `dev:web`).

---

## 1. Méthode et limite des captures

- Captures prises le 10/11/2026 via `npm run dev:web` (port 5199) + Chromium headless : `00-accueil-projets.png`, `interview/brief/hypotheses/simulation/results/settings.png`, `projects-mobile.png`.
- **Limite documentée** : sans IPC Tauri, l'app verrouille l'écran Projets tant qu'aucun projet n'existe (`App.tsx` l.612 : `view === "projects" || !activeProject ?`). Les 7 captures montrent donc le même contenu : shell + nav + écran d'entrée. Elles valident néanmoins le **socle visuel** (shell, nav, cartes, formulaires, badges, footer) et l'état vide — et révèlent un constat d'audit à part entière :

> **P1-00 — Les écrans métier (Brief, Hypothèses, Simulation, Résultats) sont inatteignables en mode web sans projet.** Conséquence pour la refonte : la phase 05 devra prévoir un *état de démonstration* (ou mock local) pour que le design des écrans data soit vérifiable dans un navigateur, sinon toute itération visuelle exigera l'app desktop complète. (Principe Snyk : les outils doivent s'intégrer au flux de travail, pas le freiner.)

## 2. Ce que montrent les captures (lecture visuelle)

| # | Constat | Gravité | Preuve |
|---|---|---|---|
| **P1-01** | **Ambiance « hero SaaS »** : gradient radial bleu en fond (haut gauche), logo `SF` en dégradé bleu + halo lumineux. Rien n'évoque des données, des mesures ou un moteur de simulation. | P1 | toutes captures, `styles.css` l.22/461 |
| **P1-02** | **Le bleu `#4f8cff` est partout** : logo, nav active, eyebrows (« ESPACE DE TRAVAIL », « PREMIER PAS », « NOUVEAU », « BIBLIOTHÈQUE »), CTA, badge `protocol 1.6.0`, barre de progression arc-en-ciel, barres de charts. Une seule couleur = aucune hiérarchie sémantique. | P1 | toutes captures |
| **P1-03** | **Aucune texture « données »** : pas de trame de grille, pas de marqueur de mesure, pas de séparateur gradué ; les cartes sont des boîtes arrondies à dégradé doux, sans rapport avec un dataset. | P1 | toutes captures |
| **P1-04** | **Chiffres absents du langage visuel** : aucun chiffre tabulaire visible, aucune unité formatée en mono sur l'écran d'entrée (pas même dans les badges d'état). | P1 | toutes captures |
| **P2-01** | **Badge « Navigateur » en rouge danger** : un état informatif (mode prévisualisation) est rendu comme une erreur. Sémantique de couleur déviée. | P2 | header des captures |
| **P2-02** | **Bouton désactivé illisible** : « Créer le projet » désactivé est un bloc bleu terne sans explication en surface (l'info est dans le hint sous le champ). | P2 | `00-accueil-projets.png` |
| **P2-03** | **Hiérarchie des eyebrows** : 4 niveaux de cartes imbriquées (carte → grille onboarding → alerte → empty state) sur l'écran d'entrée ; la lecture « premier pas » se noie dans l'empilement. | P2 | `00-accueil-projets.png` |
| **P2-04** | **Polices dépendantes de l'OS** : sur Linux (ces captures), Segoe UI est absent → fallback DejaVu. Le produit ne contrôle pas son rendu typographique. | P2 | `styles.css` l.3 |
| **P2-05** | **Placeholder tronqué** : « Une phrase pour retrouver le pr… » coupe sans ellipsis élégante dans le champ Description. | P3 | `00-accueil-projets.png` |
| **P2-06** | **Double message redondant** : « 0 projet sur cet appareil. » puis « Aucun projet enregistré. » dans le même bloc Bibliothèque. | P3 | `00-accueil-projets.png` |
| **P2-07** | **Erreur IPC en alerte pleine largeur** : « Ouvrez l'application Tauri pour accéder au stockage local et au sidecar. » — message correct (actionnable) mais présentation « danger » ambiguë avec le badge rouge Navigateur : deux alarmes pour une seule cause. | P3 | `00-accueil-projets.png` |

## 3. Problèmes structurels (du code, pas des captures)

Résumé de `inventaire-css.md` (détail complet dans ce fichier) :

| ID | Constat | Gravité |
|---|---|---|
| **S1** | 1528 lignes de CSS, **2 générations coexistantes** (séparées par un commentaire l.431), 6 paires de composants dupliqués | P1 |
| **S2** | 24 hex + 26 motifs `rgb()` + **73 écritures manuelles d'alpha** ; 10 tokens seulement dans `:root` | P1 |
| **S3** | Couleurs de **charts codées en dur dans le TSX** (`Charts.tsx` l.36–38 : P10 ambre / P50 bleu / P90 vert) — invisibles au système CSS | P1 |
| **S4** | **16 classes mortes** confirmées (~10 % du fichier) ; consommateur principal de l'ancienne génération : `ProvidersPanel.tsx` | P2 |
| **S5** | Typo : 4 écritures de la famille mono, 16 tailles px dont 7 demi-pixels, aucune échelle | P2 |
| **S6** | 5 gradients décoratifs | P2 |
| **S7** | Pas de focus visible tokenisé (inputs seulement), pas de `prefers-reduced-motion` | P2 |
| **S8** | Erreurs = `String(reason)` brut (9 occurrences, cf. `actionnabilite.md`) | P2 |

## 4. Priorisation (à consommer par les phases)

**P1 — à traiter en phase 02 (fondations)** : S1, S2, S3, P1-01, P1-02, P1-03, P1-04.
Tout part des tokens : palette encre neutre + signaux sémantiques + séries dataviz + trame. Sans ça, les écrans resteraient du SaaS repeint.

**P2 — à traiter en phases 03–05 (composants & écrans)** : S4, S5, S7, S8, P1-00, P2-01, P2-02, P2-03, P2-04.
La librairie unifiée élimine la génération 1 ; les écrans réorganisent la hiérarchie ; les erreurs deviennent actionnables.

**P3 — à traiter en phase 06 (qualité)** : P2-05, P2-06, P2-07 + contraste + focus complet + light theme.

## 5. Verdict

Le produit a une **ossature honnête** (structure claire, états vides déjà actionnables, composants TSX typés) mais son habillage est **un SaaS bleu générique** : la couleur n'exprime rien, les données ne se voient nulle part, et le code CSS porte deux générations qui se contredisent. La refonte par les tokens (phase 02) est le bon point d'entrée : c'est le seul levier qui traite P1-01/02/03/04 et S1/S2/S3 **en même temps**.

## 6. Limites de cet audit

- Les écrans métier avec **données réelles** (Hypothèses remplies, Résultats avec 3 scénarios, Sandbox avec code) n'ont pas pu être capturés : ils exigent le sidecar Python + IPC Tauri (Rust non installé sur la machine d'audit, cf. `P1-00`). À compléter si besoin avant la phase 05, ou via l'état de démonstration proposé.
- Les captures sont des états **vides** ; elles ne préjugent pas du rendu dense (listes de projets multiples, longues narrations).
