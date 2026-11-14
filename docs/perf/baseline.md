# Baseline de performance — phase 01

> Mesure de départ de la V3, sur la machine de référence modeste décrite dans [`machine-reference.md`](machine-reference.md).
> Commande : `npm run bench`. Rapport brut du run de référence : [`archive/2026-11-14-phase-01.json`](archive/2026-11-14-phase-01.json) et [`archive/2026-11-14-phase-01.md`](archive/2026-11-14-phase-01.md).

> Les durées varient de quelques pourcents entre deux exécutions sur la même machine. Ce document cite le run `latest.json` du 2026-11-14 ; seuls les ordres de grandeur et les écarts relatifs sont interprétables. `latest.json` contient désormais le run de contrôle de la phase 02 (section 8) ; le run de référence de la phase 01 est archivé sous `archive/`.

## 1. Conditions

| Élément | Valeur |
|---|---|
| Date | 2026-11-14 |
| Commit | `1b09972` |
| Moteur | 0.1.0 |
| Protocole | 1.7.0 |
| Python / NumPy | 3.14.9 / 2.5.4 |
| Scénario | `packages/engine/examples/retail_depot.json`, horizon forcé à 36 mois |
| Graine | 42 |
| Répétitions | moteur : 10 (draft), 5 (final), 2 (large) ; sidecar : 5 |

## 2. Résultats mesurés

### 2.1 Moteur (in-process)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| `draft` 500 runs × 36 mois | **9,6 ms** | 8,9 ms | 12,1 ms |
| `final` 5 000 runs × 36 mois | **63,3 ms** | 61,5 ms | 66,0 ms |
| `large` 20 000 runs × 36 mois | **249,6 ms** | 235,1 ms | 264,2 ms |
| Proxy de surface 15×15 × 200 runs | **1 700,0 ms** (225 cellules, 7,6 ms/cellule) | — | — |

- Payload `final` 5 000 runs : **13,1 Kio**.
- Mémoire du processus de bench : **112,7 Mo** (maxRSS).
- Progression : 2 callbacks pour 500 runs (granularité `batch_size = 50 000`, donc un seul lot réel).

### 2.2 Sidecar (JSON-RPC sur stdio)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| `ping` au repos | **0,64 ms** | 0,59 ms | 0,75 ms |
| `draft` 500 × 36 via RPC | **11,8 ms** | 10,2 ms | 31,3 ms |
| `final` 5 000 × 36 via RPC | **67,4 ms** | 65,4 ms | 67,8 ms |
| `ping` pendant un calcul 50 000 × 36 | **700,2 ms** (bloqué) | — | — |

- Démarrage (process → première réponse `health`) : **1 442 ms** à chaud ; ~2 600 ms à froid.
- Mémoire RSS : **67,0 Mo → 87,0 Mo**.
- Annulation : non supportée.

### 2.3 UI

Mesure **ignorée** en phase 01 : aucune infrastructure navigateur (Playwright + shim IPC) n'existe. Le rapport `ui.json` le déclare explicitement et liste les mesures prévues. Huit composants `@see/ui/viz` sont présents (lignes, histogrammes, barres, sparkline, échelle, légende).

## 3. Confrontation aux budgets du plan

| Mesure | Cible V3 | Plafond bloquant | Baseline | Verdict |
|---|---|---|---|---|
| `draft` 500 × 36 | ≤ 50 ms | 150 ms | 9,6 ms (moteur), 11,8 ms (RPC) | **très en dessous** |
| `final` 5 000 × 36 | ≤ 400 ms | 1,5 s | 63,3 ms (moteur), 67,4 ms (RPC) | **≈ 6× sous la cible** |
| Annulation | ≤ 100 ms | 250 ms | non supportée | **à livrer en phase 04/06** |
| Surface 15×15 × 200 | ≤ 8 s | 20 s | 1,70 s (proxy, non CRN) | **plausible, à confirmer phase 11** |
| Mise à jour graphique | ≤ 16 ms | 33 ms | non mesurée | **phase 08/09** |
| Mémoire sidecar | ≤ 500 Mo | 800 Mo | 87,0 Mo après calculs | **large marge** |
| Démarrage sidecar | à consigner | — | 1,4 s chaud / 2,6 s froid | **à optimiser si l'app dépasse 10 s** |

## 4. Interprétation

1. **Le budget `draft` est confortable.** À ~10 ms pour 500 runs × 36 mois, un glissement à 30–60 i/s n'est pas limité par le calcul moteur. Le facteur limitant sera l'IPC, la sérialisation et le rendu — d'où la phase 06.
2. **Le `final` tient largement la cible.** 63 ms laisse de la marge pour les métriques supplémentaires de la phase 02 (bandes mensuelles, échantillon de runs) et pour les événements de la phase 05.
3. **La surface par défaut est réaliste.** Le proxy à 1,70 s pour 225 cellules suggère qu'une vraie surface 15×15 × 200 restera sous 8 s, même avec un surcoût par point. La grille 25×25 × 300 de la spec reste une option coûteuse, pas le défaut.
4. **Le blocage mono-thread est mesuré et confirmé.** Un `ping` envoyé pendant un calcul 50 000 × 36 attend 700 ms. C'est le constat C3 : tant que `rpc.py` reste mono-thread, aucun flux partiel ni aucune annulation n'est possible. La phase 06 est indispensable avant le cockpit.
5. **La mémoire n'est pas un risque à court terme.** 87 Mo pour le sidecar laisse une marge importante avant le plafond de 500 Mo, même avec un cache de runs et un échantillon de trajectoires.
6. **Le démarrage doit être surveillé.** 1,4 s pour le sidecar seul est acceptable, mais l'application complète (WebView + chargement du sidecar + projet) doit rester sous la cible de la phase 16. À mesurer côté Tauri.

## 5. Constats d'audit confirmés par la mesure

- `sample_hypothesis` **ignore `value`** quand `distribution` est présente : déplacer la valeur d'une hypothèse sans supprimer sa distribution ne change **aucun** tirage. C'est un piège d'UX majeur pour le cockpit à trois poignées (phase 09) et une raison de figer la sémantique en phase 02/03.
- Le moteur ne publie que `simulate.progress` (fraction), sans agrégats partiels ni annulation.
- Le sidecar persiste chaque run complet dans SQLite via `project_service.simulate()` : le `draft` devra être explicitement exclu en phase 06/07.
- Le protocole est en `1.7.0` et ne connaît pas `simulation.start` / `simulation.cancel`.

## 6. Reproductibilité

```bash
npm run bench          # les trois bancs + agrégation
npm run bench:engine   # moteur seul
npm run bench:sidecar  # sidecar seul
npm run bench:ui       # rapport UI (ignoré en phase 01)
```

Les fichiers `engine.json`, `sidecar.json` et `ui.json` sont écrasés à chaque exécution ; `latest.json` et `latest.md` agrègent l'ensemble. Pour comparer deux commits, copier `latest.json` sous un nom daté avant de relancer.

## 7. Prochaine mesure attendue

À la fin de la phase 04, rejouer `npm run bench` et vérifier :

- `draft` toujours ≤ 50 ms avec les nouvelles métriques ;
- annulation ≤ 100 ms (nouveau banc à ajouter) ;
- taille d'un partiel < 50 Kio ;
- `final` ≤ 400 ms malgré les bandes mensuelles et l'échantillon.

À la fin de la phase 11, mesurer la **vraie** surface CRN et confirmer ou réduire la grille par défaut.

## 8. Contrôle après la phase 02 (2026-11-14)

Run `npm run bench` exécuté sur `addbd29` avec les changements de la phase 02 non encore
commités (protocole `1.8.0`, métriques cockpit, échantillon de runs). Rapport brut :
[`latest.json`](latest.json), [`latest.md`](latest.md).

| Mesure | Phase 01 | Phase 02 | Écart | Budget |
|---|---|---|---|---|
| `draft` 500 × 36 (moteur) | 9,6 ms | **12,9 ms** | +34 % | ≤ 50 ms |
| `final` 5 000 × 36 (moteur) | 63,3 ms | **75,3 ms** | +19 % | ≤ 400 ms |
| `large` 20 000 × 36 (moteur) | 249,6 ms | **242,9 ms** | −3 % | — |
| Surface proxy 15×15 × 200 | 1 700 ms | **2 237 ms** | +32 % | ≤ 8 s |
| Payload `final` | 13,1 Kio | **28,0 Kio** | +114 % | < 100 Kio |
| `draft` RPC sidecar | 11,8 ms | **15,9 ms** | +35 % | ≤ 50 ms |
| `final` RPC sidecar | 67,4 ms | **78,6 ms** | +17 % | ≤ 400 ms |
| Démarrage sidecar | 1 442 ms | **654 ms** | −55 % | à consigner |
| Mémoire sidecar | 87,0 Mo | **72,0 Mo** | — | ≤ 500 Mo |

Lecture :

- les budgets produit restent largement tenus : `draft` ≈ 4× sous la cible, `final` ≈ 5× sous
  la cible, payload ≈ 3,5× sous le plafond de 100 Kio ;
- le surcoût relatif vient surtout du calcul des bandes mensuelles (~5 ms), de la CDF et de
  la construction des objets mensuels, pas de la collecte par run ;
- la surface augmente mécaniquement avec le coût par point ; elle reste sous 8 s et sera
  réévaluée avec les tirages communs en phase 11 ;
- la variance de démarrage du sidecar est forte sur cette machine ; la mesure phase 02 est
  plus favorable, sans optimisation dédiée.

Prochaine mesure : fin de phase 04, avec le banc d'annulation et les partiels.
