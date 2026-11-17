# Sourcing du pack CG — brouillon `2026.2`

> Statut : **brouillon non signé**, prêt pour revue. Voir D3 de
> [`decisions-lancement.md`](../01-audit-et-decisions/decisions-lancement.md).
> Règles de fiabilité : [ADR 0009](../../adr/0009-gouvernance-benchmarks.md).

## 1. Ce qui change en `2026.2`

- Le panier de référence ne contient plus que des produits réellement suivis par
  WFP/HDX pour Brazzaville : riz, farine de manioc, haricots blancs, huile
  végétale, sel. Le **sucre** est retiré : il n'existe aucune série WFP pour le
  Congo, et le chiffrer « au cadrage » revenait à inventer une source.
- `unit_price` est **recalculé** sur les 12 derniers mois publiés
  (octobre 2025 – septembre 2026) : médiane **14 195,5 XAF**, arrondie à
  **14 200 XAF**, bornes **12 636 – 16 883 XAF**. Fiabilité passée à `study`.
- `unit_cost` suit le prix du panier (85 % du détail, marge brute de 15 %) et
  reste `estimate`, faute de prix de gros public pour Brazzaville.
- `fixed_costs_monthly` conserve le loyer observé à Moungali (150 000 XAF/mois)
  et documente les charges par la grille E2C ; la valeur reste `estimate`.
- `demand_mean_monthly`, `demand_cv` et `loss_rate` restent `estimate` : aucune
  série publique ne mesure la fréquentation, la variabilité ou la démarche d'une
  boutique de quartier. Elles sont désormais datées, justifiées et bornées.
- `publishedAt` et les dates de source des estimations passent au 2026-11-17.

Fichier : [`data/benchmark-packs/drafts/cg-brazzaville-retail-2026.2.json`](../../../data/benchmark-packs/drafts/cg-brazzaville-retail-2026.2.json).

Le dossier `drafts/` n'est pas scanné par le sidecar : le pack `2026.1` continue
d'alimenter l'application tant que `2026.2` n'est pas signé.

## 2. Tableau de sourcing

| Indicateur | Valeur | Fiabilité | Source / méthode | Remplaçable publiquement ? |
|---|---|---|---|---|
| `unit_price` | 14 200 XAF/panier | `study` | WFP/HDX, prix de détail Brazzaville, 12 mois à septembre 2026 | **Oui** — recalcul déterministe |
| `unit_cost` | 12 070 XAF/panier | `estimate` | 85 % du prix de détail ; transport et pertes inclus | **Non** — pas de série de gros Congo |
| `gross_margin` | 0,15 (10–22 %) | `estimate` | Cadrage petit commerce ; ancrage sur le détail WFP | **Non** — marge de gros non publiée |
| `fixed_costs_monthly` | 200 000 XAF/mois | `estimate` | Loyer Moungali (150 000) + charges estimées (E2C) | **Partiel** — loyer oui, consommation non |
| `demand_mean_monthly` | 220 paniers/mois | `estimate` | ~10 paniers/jour ouvré | **Non** — enquête terrain requise |
| `demand_cv` | 0,25 (0,15–0,40) | `estimate` | Variabilité de proximité, saisonnalité incluse | **Non** — pas de mesure publique |
| `loss_rate` | 0,04 (0,02–0,08) | `estimate` | Borne prudente, ancrée sur FAO 12.3.1a (19,9 % avant détail en Afrique subsaharienne) | **Non** — part détail non mesurée |

## 3. Rejouer le calcul WFP

Le script [`wfp_basket.py`](../../../data/benchmark-packs/tools/wfp_basket.py)
télécharge le CSV WFP/HDX (ou lit un fichier local) et agrège le panier :

```powershell
uv run --project packages/benchmarks python data/benchmark-packs/tools/wfp_basket.py --months 12 --json
```

Résultat au 2026-11-17 :

```json
{
  "firstMonth": "2025-10-15",
  "lastMonth": "2026-09-15",
  "median": 14195.5,
  "min": 12636.0,
  "max": 16883.0
}
```

Le CSV est celui du dataset HDX
[WFP food prices for Congo](https://data.humdata.org/dataset/wfp-food-prices-for-congo).
Seuls les marchés de l'`admin1` Brazzaville sont retenus ; un mois n'entre dans
la fenêtre que si les cinq produits y sont tous présents.

## 4. Ce qui relève de l'enquête utilisateur

Les valeurs `estimate` ne doivent **pas** être présentées comme des sources
publiques. Le parcours d'onboarding doit demander à l'utilisateur :

- prix d'achat et de vente réels (factures fournisseur) → `unit_cost`,
  `gross_margin` ;
- ventes mensuelles et nombre de clients → `demand_mean_monthly`, `demand_cv` ;
- inventaires et démarque → `loss_rate` ;
- loyer, électricité, eau, sécurité → `fixed_costs_monthly`.

Tant que ces données ne sont pas saisies, le projet d'exemple reste un
**cadrage pédagogique**, pas une prévision.

## 5. Mise en service (bloquée sur la clé)

1. Revue du JSON par le responsable signature.
2. Signature Ed25519 avec la clé hors dépôt :
   `uv run --project packages/benchmarks python data/benchmark-packs/tools/sign_pack.py <pack> <clé-privée>`
3. Vérification :
   `uv run --project packages/benchmarks python data/benchmark-packs/tools/verify_pack.py <pack>`
4. Déplacement de `drafts/` vers `packs/`, conservation de `2026.1` si une
   compatibilité est nécessaire.
5. Mise à jour des tests qui citent `2026.1` et `13 850` :
   `apps/desktop/src-tauri/sidecar/tests/test_benchmarks.py` (valeur et
   signature altérée) et `test_rpc.py` (liste des packs).
6. Re-vérification des **deux** packs embarqués.

La clé privée n'est pas sur la machine de développement au 2026-11-17 : la clé
publique versionnée ne permet pas de signer. Le porteur de clé doit être
identifié avant la phase 15.

## 6. Gouvernance signature (état au 2026-11-17)

- Responsable signature : **porteur du projet** (décision du 2026-11-17).
- Suppléant : **à confirmer**.
- Entité signataire et pays de dépôt : **à préciser** avant le devis ferme.
- Vérification d'identité : pièces prêtes, démarche à lancer avec l'AC retenue.

Voir [`signature-windows.md`](../01-audit-et-decisions/signature-windows.md) §8.

## 7. Vérification des packs embarqués (2026-11-17)

```text
OK keyId=seefuture-benchmark-2026 sha256=c4006bb9f1b5ef732c77c444e09a6795f19782cc9c6dbf2dfa62840a3d7427e4  (CG 2026.1)
OK keyId=seefuture-benchmark-2026 sha256=52d2cab9030bd378f127e664ff79be9efef5b30f4de2b3e4e167221d4f5c5202  (CF 2026.1)
```
