# Projet d'exemple — dépôt de revente à Brazzaville

> **Statut** : modèle pédagogique prêt à importer. Les chiffres sourcés viennent
> du pack signé `cg-brazzaville-retail-2026.1`. Les estimations de cadrage sont
> explicitement marquées comme telles et doivent être remplacées par les données
> de l'utilisateur.

## 1. À quoi sert ce modèle

Il permet à un nouvel utilisateur d'obtenir un premier résultat crédible en
moins de deux minutes, hors ligne, sans fournisseur IA :

1. importer le projet depuis l'écran **Projets** ;
2. lire les hypothèses et leur provenance ;
3. lancer un calcul final avec la graine `42` ;
4. comparer la branche « Prix -10 % » ;
5. exporter le dossier Markdown.

Le modèle reste un **cadrage** : aucune ligne ne prétend prévoir les ventes
réelles du quartier.

## 2. Contenu du fichier

[`template.json`](template.json) contient :

| Bloc | Rôle |
|---|---|
| `brief` | brief validé (problème, client, offre, revenus, coûts, géographie) |
| `scenario` | scénario `retail_depot`, devise **XAF**, horizon **36 mois**, 3 événements |
| `branches` | une variante « Prix -10 % » avec ses hypothèses explicites |
| `seed` | graine de démonstration `42` |
| `initialVersionLabel` | libellé de la version nommée créée à l'import |

L'import génère toujours de **nouveaux identifiants** : le modèle n'est jamais
partagé entre projets par référence.

## 3. Sourcing

| Hypothèse | Valeur | Fiabilité | Source |
|---|---|---|---|
| `unit_price` | 13 850 XAF/panier | `study` | WFP/HDX, prix de détail Brazzaville, avril 2026 |
| `unit_cost` | 11 770 XAF/panier | `estimate` | 85 % du prix de détail, transport et pertes inclus |
| `fixed_costs_monthly` | 200 000 XAF/mois | `estimate` | Loyer observé à Moungali + charges estimées |
| `demand_mean_monthly` | 220 paniers/mois | `estimate` | Cadrage See The Future, à mesurer |
| `demand_cv` | 0,25 | `estimate` | Variabilité de proximité |
| `loss_rate` | 0,04 | `estimate` | Démarque et pertes |
| `initial_cash` | 2 500 000 XAF | hypothèse | Apport simulé |

Le détail du calcul WFP et le brouillon `2026.2` sont documentés dans
[`../../docs/V2/15-onboarding-exemple-pitch/sourcing-pack-cg.md`](../../docs/V2/15-onboarding-exemple-pitch/sourcing-pack-cg.md).

> Le pack `2026.2` n'est pas encore signé : l'exemple utilise donc `2026.1`,
> vérifiable hors ligne avec la clé publique versionnée. Le passage à `2026.2`
> ne changera que les valeurs du pack, pas la structure du modèle.

## 4. Événements

| Id | Type | Mois | Durée | Effet | Probabilité |
|---|---|---|---|---|---|
| `prix_fournisseur` | hausse du prix fournisseur | 8 | 3 mois | coût d'achat ×1,05 à ×1,30 | 60 % |
| `coupures` | coupure d'électricité | 3 | 2 mois | pertes +1 à +5 points | 40 % |
| `pic_fetes` | pic de demande | 12 | 1 mois | demande ×1,10 à ×1,60 | 30 % |

Les événements sont désactivables dans l'interface ; un événement désactivé ne
consomme aucun tirage et ne modifie pas les hypothèses (ADR 0010, 0015).

## 5. Limites assumées

- La demande, la variabilité et les pertes ne viennent d'aucune série publique :
  ce sont des estimations de cadrage.
- Le prix du panier est un panier de référence, pas le prix d'un produit unique.
- Le modèle ne modélise ni le crédit client, ni la fiscalité réelle, ni la
  saisonnalité propre à un quartier précis.
- Les résultats ne sont pas une prévision garantie.

## 6. Reproductibilité

Même graine (`42`), même version de moteur et même scénario donnent les mêmes
chiffres. Le dossier exporté rappelle la graine, la version du moteur et le
`runId` pour permettre la vérification (ADR 0018).
