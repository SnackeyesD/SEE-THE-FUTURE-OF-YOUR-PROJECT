# Décisions de lancement — 2026-11-17

> Ce document tranche les points « Reste à décider » de la phase 01 (§11 du [README](README.md)) :
> calendrier/effectifs, ordre de sacrifice, projet d'exemple, signature Windows, mesure UI.
>
> **Statut** : accepté le 2026-11-17 (produit + direction).
> **Références** : [`docs/V2/PLAN-IMPLEMENTATION-V3.md`](../PLAN-IMPLEMENTATION-V3.md) §7–§10, [`signature-windows.md`](signature-windows.md), [`docs/V2/15-onboarding-exemple-pitch/README.md`](../15-onboarding-exemple-pitch/README.md), [`docs/V2/16-durcissement-lancement/README.md`](../16-durcissement-lancement/README.md), `data/benchmark-packs/packs/`.

---

## D1 — Calendrier et effectifs : scénario 3 / 2 / 1 et date de janvier

**Décision** : on retient le **scénario 3 devs + 0,5 produit** comme engagement, avec le **jalon D (lancement) au vendredi 15 janvier 2027**.

| Scénario | Durée | Livraison | Décision |
|---|---|---|---|
| 3 devs + 0,5 produit | 7–8 semaines | **15 janvier 2027** (cible retenue) | ✅ engagé |
| 2 devs | 10–12 semaines | février 2027 | fallback annoncé dès maintenant si l'effectif baisse |
| 1 dev | 17–21 semaines | mars 2027 | janvier abandonné d'office ; 3D et pitch coupés (voir D2) |

- Le calendrier inclut les fêtes : la marge de **20 %** du plan §8 est intégrée dans la date du 15 janvier (démarrage mi-novembre 2026, phases 01–03 déjà réalisées).
- Jalons indicatifs : **A** (cockpit 2D, phase 09) ≈ 12 décembre 2026 ; **B** (analyse interactive, phase 11) ≈ 26 décembre 2026 ; **D** (lancement, phase 16) = 15 janvier 2027.
- Règle de dérive : si le jalon A glisse de **plus de 5 jours**, l'ordre de sacrifice D2 s'applique **sans re-débat**.

## D2 — Périmètre janvier : ordre de sacrifice du plan §7 (signé)

Ordre de coupe figé, du premier au dernier :

1. **Phase 14 entière** (vue 3D + nuage 3D) — première coupe ; le **repli 2D (heatmap) reste obligatoire** et livré.
2. **Mode pitch** (partie D2 de la phase 15) — l'onboarding et le projet d'exemple sont conservés (indispensables pour janvier).
3. **Phase 11 réduite** à la heatmap 2D + objectif mono-levier.

**Jamais coupés** : phases 02–09 (moteur réactif + cockpit 2D), tests de reproductibilité/CRN/golden, phase 16 (durcissement & lancement).

## D3 — Projet d'exemple : Brazzaville (CG), devise **XAF**

- **Secteur retenu : Brazzaville, Congo (CG)** — pack `cg-brazzaville-retail-2026.1` préféré à `cf-bangui-retail-2026.1` : sources plus fraîches (WFP/HDX avril 2026 et annonce de loyer Moungali novembre 2026 = `fresh`, contre des sources d'août 2025 = `aging` pour Bangui, règle ADR 0009).
- Livrable renommé : `data/examples/retail-depot-brazzaville/` (au lieu de `retail-depot-bangui/` dans le README de la phase 15).
- **Devise : XAF conservé** — Brazzaville est en zone CEMAC (XAF), pas XOF. Le projet d'exemple pose `currency: "XAF"` explicitement ; le défaut `XOF` du moteur ne couvre pas la cible CEMAC et reste documenté comme tel.
- **Sourcing avant la phase 15** : le brouillon `2026.2` est prêt ([`sourcing-pack-cg.md`](../15-onboarding-exemple-pitch/sourcing-pack-cg.md)) : `unit_price` recalculé sur WFP/HDX, panier ramené aux cinq produits réellement suivis, autres `estimate` documentés et datés. Restent la **re-signature Ed25519** (`tools/sign_pack.py`) et le déplacement vers `packs/`, bloqués par la clé privée absente de la machine de développement. Les deux packs embarqués ont été vérifiés le 2026-11-17 (`keyId=seefuture-benchmark-2026`).

## D4 — Signature Windows : OV + AC classique + token USB, vérification d'identité lancée maintenant

- **Certificat retenu : OV** (ordre de grandeur 250–500 €/an, 1–3 semaines) sur **token matériel USB** via une **AC classique reconnue** (DigiCert, Sectigo ou GlobalSign), avec **horodatage RFC 3161**. Depuis 2023, aucun certificat de signature de code en fichier simple n'est émis.
- **EV** : option uniquement si le budget le permet et si la réputation SmartScreen au lancement est jugée critique (400–900 €/an, 2–5 semaines).
- **Azure Trusted Signing écarté** pour l'instant : éligibilité incertaine (3 ans d'ancienneté vérifiable + compte Azure) et dépendance cloud pour la CI de signature.
- **Vérification d'identité lancée en phase 01–02** (même si la signature n'est appliquée qu'en phase 16) : pièces prêtes — registre de commerce, pièce d'identité, justificatif d'adresse, domaine, téléphone ; **devis avec délai ferme demandé en phase 01**.
- **Responsable signature : porteur du projet** (décision du 2026-11-17) ; suppléant, entité signataire et pays de dépôt encore à préciser. Token au coffre, procédure de réémission documentée.
- Intégration CI (accès token/HSM sans exposer la clé) et test sur **VM Windows propre** restent en phase 16.
- **Plan B** : si le certificat n'est pas prêt en phase 16, beta interne non signée avec empreinte SHA-256 publiée, ou ZIP portable + empreinte ; **jamais de binaire public non signé**, jamais de certificat auto-signé pour le public.
- La checklist §8 de [`signature-windows.md`](signature-windows.md) est remplie en conséquence.

## D5 — Mesure UI : Vitest + Testing Library maintenant, Playwright en phase 16

- **Dès maintenant (phases 08–15)** : Vitest + Testing Library pour tout test unitaire/composant (déjà en place : `vitest`, `@testing-library/react`, 14 tests verts au 2026-11-17). Règle : chaque nouvel écran et chaque commande du cockpit arrive avec son test composant ; la couverture existante (App, ResultsScreen, SimulationScreen, narration) ne baisse pas.
- **Phase 16 uniquement** : Playwright E2E en mode web (`dev:web`) avec **shim IPC déterministe**, parcours critiques uniquement (onboarding → hypothèses → simulation → résultats → export), taux d'échec < 2 %, aucun test flaky toléré.
- Aucun nouvel outil de test avant la phase 16 ; la mesure de perf UI éventuelle passe par `npm run bench:ui`. `npm run ui:check` reste le garde-fou design tokens en CI.

---

## Suivi

| Décision | Où c'est consigné | Prochaine étape |
|---|---|---|
| D1 calendrier | ce document | jalon A le 2026-12-12 |
| D2 sacrifice | ce document + plan §7 | appliquer si jalon A glisse > 5 j |
| D3 exemple CG/XAF | ce document + [`sourcing-pack-cg.md`](../15-onboarding-exemple-pitch/sourcing-pack-cg.md) | brouillon 2026.2 prêt ; signature et déplacement avant phase 15 |
| D4 signature | ce document + `signature-windows.md` §8 | responsable = porteur du projet ; suppléant/entité/pays puis devis et vérification d'identité |
| D5 tests UI | ce document + README phase 16 | aucun changement d'outil avant phase 16 |
