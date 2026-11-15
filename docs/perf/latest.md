# Baseline de performance — V3

> Généré par `npm run bench` le 2026-11-15T05:18:28.641Z.
> Ne pas éditer à la main : relancer le banc d'essai.

## Machine et versions

| Élément | Valeur |
|---|---|
| CPU | Intel(R) Pentium(R) CPU 6405U @ 2.40GHz (4 threads) |
| RAM | 7742 Mo |
| OS | Linux-7.1.1-76070101-generic-x86_64-with-glibc2.35 |
| Python | 3.14.9 |
| NumPy | 2.5.4 |
| Moteur | 0.3.0 |
| Protocole | 1.8.0 |
| Commit | bfbbb3e |

## Moteur (in-process)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| draft 500 × 36 | 26.139 ms | 21.058 ms | 31.538 ms |
| final 5 000 × 36 | 167.631 ms | 157.684 ms | 179.068 ms |
| large 20 000 × 36 | 661.993 ms | 572.22 ms | 751.765 ms |
| surface proxy 15×15 × 200 | 4030.505 ms (225 cellules) | — | — |

- Payload final 5 000 runs : **28.2 Kio**.
- Mémoire du processus de bench : **76.5 Mo**.
- Progression : 3 callback(s) pour 500 runs.
- Partiels : 20 messages, payload max **26.1 Kio**, calcul max **18.323 ms**, écart max **29.686 ms**.
- Annulation : supported, médiane **0.168 ms**, max **0.184 ms** après 512 runs.
- Convergence (`final`) : non, stabilité 0, 0 bloc(s) stable(s).
- Audit : `value` **ignoré** quand une distribution existe.

## Sidecar (JSON-RPC sur stdio)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| ping au repos | 0.619 ms | 0.552 ms | 1.239 ms |
| draft 500 × 36 via RPC | 32.086 ms | 21.916 ms | 55.719 ms |
| final 5 000 × 36 via RPC | 190.782 ms | 180.92 ms | 216.499 ms |

- Démarrage (process → `health`) : **862.91 ms**.
- **Blocage mono-thread** : un `ping` envoyé pendant un calcul 50 000 × 36 attend **1250.273 ms**. Constat C3, correction en phase 06.
- Mémoire RSS : 63.8 Mo → 73.2 Mo.
- Annulation : moteur prêt (phase 04), transport sidecar en phase 06.

## UI

- **Mesure ignorée** : aucune infrastructure navigateur (Playwright + shim IPC déterministe) : la mesure fps/latence serait inventée. Créée en phase 08 (Vitest) puis 16 (Playwright).
- Composants `@see/ui/viz` présents : 8.
- Bundle `apps/desktop/dist` : 1477.4 Kio.
- Mesures prévues :
  - fps médian pendant un glissement de curseur (cible 30–60 i/s)
  - temps de mise à jour du FanChart 36 points + 3 fantômes (cible ≤ 16 ms)
  - temps de traitement d'un partiel (cible ≤ 4 ms)
  - mémoire UI (cible < 100 Mo)
  - taille du chunk 3D gzip (cible < 1,2 Mo, phase 14)

## Lecture et limites

- Les mesures moteur sont **in-process** ; celles du sidecar incluent JSON-RPC et la validation.
- Le « surface proxy » rend les deux axes déterministes (`distribution = None`) : il mesure le **temps**, pas une vraie surface en tirages communs (phase 11).
- Le moteur expose depuis la phase 04 l'annulation et les partiels ; leur transport JSON-RPC reste planifié en phase 06.
- L'écart entre partiels inclut le calcul du bloc courant, pas seulement la construction du partiel.
- Une mesure UI réelle exige un navigateur piloté ; elle est planifiée en phase 08/16.
- Comparer deux exécutions sur la **même machine** ; les durées varient avec la charge système.

