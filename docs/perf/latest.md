# Baseline de performance — V3

> Généré par `npm run bench` le 2026-11-14T08:32:12.957Z.
> Ne pas éditer à la main : relancer le banc d'essai.

## Machine et versions

| Élément | Valeur |
|---|---|
| CPU | Intel(R) Pentium(R) CPU 6405U @ 2.40GHz (4 threads) |
| RAM | 7742 Mo |
| OS | Linux-7.1.1-76070101-generic-x86_64-with-glibc2.35 |
| Python | 3.14.9 |
| NumPy | 2.5.4 |
| Moteur | 0.1.0 |
| Protocole | 1.8.0 |
| Commit | addbd29 |

## Moteur (in-process)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| draft 500 × 36 | 12.892 ms | 12.429 ms | 14.089 ms |
| final 5 000 × 36 | 75.347 ms | 73.169 ms | 77.749 ms |
| large 20 000 × 36 | 242.915 ms | 241.858 ms | 243.972 ms |
| surface proxy 15×15 × 200 | 2237.028 ms (225 cellules) | — | — |

- Payload final 5 000 runs : **28 Kio**.
- Mémoire du processus de bench : **123.2 Mo**.
- Progression : 2 callback(s) pour 500 runs.
- Annulation : not_supported (phase 04).
- Audit : `value` **ignoré** quand une distribution existe.

## Sidecar (JSON-RPC sur stdio)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| ping au repos | 0.656 ms | 0.564 ms | 0.693 ms |
| draft 500 × 36 via RPC | 15.882 ms | 14.988 ms | 142.063 ms |
| final 5 000 × 36 via RPC | 78.572 ms | 77.802 ms | 80.071 ms |

- Démarrage (process → `health`) : **654.292 ms**.
- **Blocage mono-thread** : un `ping` envoyé pendant un calcul 50 000 × 36 attend **647.174 ms**. Constat C3, correction en phase 06.
- Mémoire RSS : 63.6 Mo → 72 Mo.
- Annulation : non supportée (phase 04/06).

## UI

- **Mesure ignorée** : aucune infrastructure navigateur (Playwright + shim IPC déterministe) : la mesure fps/latence serait inventée. Créée en phase 08 (Vitest) puis 16 (Playwright).
- Composants `@see/ui/viz` présents : 8.
- Bundle `apps/desktop/dist` : absent (build non lancé).
- Mesures prévues :
  - fps médian pendant un glissement de curseur (cible 30–60 i/s)
  - temps de mise à jour du FanChart 36 points + 3 fantômes (cible ≤ 16 ms)
  - temps de traitement d'un partiel (cible ≤ 4 ms)
  - mémoire UI (cible < 100 Mo)
  - taille du chunk 3D gzip (cible < 1,2 Mo, phase 14)

## Lecture et limites

- Les mesures moteur sont **in-process** ; celles du sidecar incluent JSON-RPC et la validation.
- Le « surface proxy » rend les deux axes déterministes (`distribution = None`) : il mesure le **temps**, pas une vraie surface en tirages communs (phase 11).
- L'absence d'annulation et de flux partiels est un constat de la phase 01, pas une régression.
- Une mesure UI réelle exige un navigateur piloté ; elle est planifiée en phase 08/16.
- Comparer deux exécutions sur la **même machine** ; les durées varient avec la charge système.

