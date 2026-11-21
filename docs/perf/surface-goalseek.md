# Banc phase 11 — surface 2D et recherche d'objectif

## Contexte

- Date de mesure : **2026-11-21**.
- Base Git : `1f58733` (`v3/analyse-interactive`), avec les correctifs UI en cours dans le working tree ; le code moteur mesuré est inchangé.
- Moteur : `0.4.0`.
- Machine : machine de référence modeste décrite dans [`machine-reference.md`](machine-reference.md).
- Méthode : deux exécutions consécutives, seconde retenue conformément à la procédure du projet. Aucune autre tâche de test lourde ne tournait pendant le banc.

Commande rejouée :

```bash
uv run --project packages/engine python packages/engine/bench/bench_surface_goalseek.py
```

Le scénario est déterministe : 12 mois, 10 unités/mois, marge `prix − coût`, graine `42`. Les deux passages produisent la même matrice et le même meilleur point.

## Résultats

| Banc | Passage 1 | Passage 2 retenu | Cible | Plafond | Verdict |
|---|---:|---:|---:|---:|---|
| Surface 15×15 × 200 runs — 45 000 runs | 1,562 s | **1,504 s** | ≤ 8 s | 20 s | ✅ |
| Goal seek mono-levier, 18 évaluations draft × 500 runs + confirmation finale × 5 000 runs | 0,232 s | **0,208 s** | ≤ 3 s | 8 s | ✅ |

La recherche s'est terminée sans épuiser son budget de 80 évaluations : `feasible=true`, `budgetExhausted=false`, meilleur point `unit_price=15`, valeur confirmée `profit_p50=1 200`, qualité `final`.

## Lecture

- La vraie surface CRN est plus rapide que le proxy historique de la phase 01 sur cette exécution et reste très en dessous du budget de 8 s.
- Le temps de goal seek inclut les 18 évaluations uniques et la confirmation finale du meilleur point.
- Ces mesures ne couvrent ni le coût IPC ni le rendu de la heatmap ; elles valident les budgets moteur uniquement.
- Les valeurs absolues restent dépendantes de la charge système. La comparaison de release devra être rejouée sur la même machine, dans des conditions équivalentes.
