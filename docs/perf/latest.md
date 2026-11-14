# Baseline de performance — V3

> Généré par `npm run bench` le 2026-11-14T19:13:52.689Z.
> Ne pas éditer à la main : relancer le banc d'essai.

## Machine et versions

| Élément | Valeur |
|---|---|
| CPU | Intel(R) Pentium(R) CPU 6405U @ 2.40GHz (4 threads) |
| RAM | 7742 Mo |
| OS | Linux-7.1.1-76070101-generic-x86_64-with-glibc2.35 |
| Python | 3.14.9 |
| NumPy | 2.5.4 |
| Moteur | 0.2.0 |
| Protocole | 1.8.0 |
| Commit | 79fe9b2 |

## Moteur (in-process)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| draft 500 × 36 | 14.37 ms | 13.497 ms | 15.135 ms |
| final 5 000 × 36 | 77.596 ms | 76.212 ms | 79.06 ms |
| large 20 000 × 36 | 252.137 ms | 250.138 ms | 254.137 ms |
| surface proxy 15×15 × 200 | 2523.691 ms (225 cellules) | — | — |

- Payload final 5 000 runs : **28 Kio**.
- Mémoire du processus de bench : **128 Mo**.
- Progression : 2 callback(s) pour 500 runs.
- Annulation : not_supported (phase 04).
- Audit : `value` **ignoré** quand une distribution existe.

## Sidecar (JSON-RPC sur stdio)

| Mesure | Médiane | Min | Max |
|---|---|---|---|
| ping au repos | 0.676 ms | 0.583 ms | 0.697 ms |
| draft 500 × 36 via RPC | 16.937 ms | 16.121 ms | 36.316 ms |
| final 5 000 × 36 via RPC | 80.227 ms | 77.856 ms | 81.219 ms |

- Démarrage (process → `health`) : **653.838 ms**.
- **Blocage mono-thread** : un `ping` envoyé pendant un calcul 50 000 × 36 attend **639.397 ms**. Constat C3, correction en phase 06.
- Mémoire RSS : 63.7 Mo → 77.2 Mo.
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

