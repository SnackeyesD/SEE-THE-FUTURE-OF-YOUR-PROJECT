# Machine de référence — mesures de performance

> Définit la machine sur laquelle les budgets de la V3 sont mesurés et la procédure pour rejouer une mesure comparable.

## 1. Pourquoi une machine de référence

Les budgets du plan (`draft` ≤ 50 ms, `final` ≤ 400 ms, surface ≤ 8 s) ne veulent rien dire sur un poste de développement rapide. Ils sont calibrés sur une **machine modeste de 2018–2020**, représentative des utilisateurs cibles :

- 2 cœurs / 4 threads, ~2,4 GHz ;
- 8 Go de RAM ;
- pas de GPU dédié ;
- SSD SATA ;
- Windows 11 ou Linux (WebKitGTK).

## 2. Machine utilisée pour la baseline de la phase 01

| Élément | Valeur |
|---|---|
| Modèle CPU | Intel Pentium 6405U @ 2,40 GHz (2 cœurs, 4 threads) |
| RAM | 7 742 Mo (~7,6 Gio) |
| GPU | Intel UHD Graphics 610 (intégré, pas de GPU dédié) |
| OS | Pop!_OS 22.04 LTS, noyau Linux 7.1.1 |
| Python | 3.14.9 (via `uv`), NumPy 2.5.4 |
| Node | 26.13.0 |
| Stockage | SSD |

Cette machine **sert de machine de référence modeste** pour la V3 : elle est dans la fourchette basse de la cible. Toute mesure de release (phase 16) doit être rejouée dessus ou sur une machine équivalente.

> La RAM disponible observée pendant les mesures peut être faible (navigateur et outils ouverts). Pour une mesure de référence, fermer les applications lourdes et vérifier `free -h` avant de lancer `npm run bench`.

## 3. Procédure de mesure

1. Se placer sur le commit à mesurer, arbre propre.
2. Fermer les Applications lourdes (navigateur, IDE, conteneurs).
3. Sur secteur, performance « équilibrée » ou « haute », pas de mode économie.
4. Lancer **deux fois** `npm run bench` : la première exécution paie les imports à froid et la construction des environnements `uv`. Ne retenir que la seconde.
5. Comparer uniquement des mesures prises sur la **même machine**, au même commit de référence, avec la même version de Python/NumPy.
6. Consigner la médiane ; les extrêmes servent à détecter une perturbation, pas à comparer.
7. Archiver `docs/perf/latest.json` et `latest.md` avec le commit.

## 4. Ce que mesure chaque banc

| Banc | Ce qu'il mesure | Ce qu'il ne mesure pas |
|---|---|---|
| `bench:engine` | moteur in-process : draft, final, large, proxy de surface, payload, mémoire | le coût IPC, la validation, l'UI |
| `bench:sidecar` | sidecar réel en JSON-RPC : démarrage, ping, simulate, blocage mono-thread, RSS | le coût Tauri/Rust, le rendu |
| `bench:ui` | inventaire dataviz et taille de bundle si un build existe | fps et latence de rendu (infrastructure navigateur absente en phase 01) |

## 5. Limites connues

- Le « surface proxy » (15×15 × 200) rend les deux axes déterministes (`distribution = None`) : il mesure le **coût d'appel répété**, pas une surface en tirages communs. La vraie surface est mesurée en phase 11.
- Le démarrage du sidecar dépend du cache disque : première exécution à froid ~2,6 s, exécutions suivantes ~1,0 s.
- Les mesures UI seront ajoutées en phase 08 (Vitest) et phase 16 (Playwright + shim IPC).
- Les chiffres absolus varient avec la charge système ; seuls les écarts relatifs sur une machine stable sont interprétables.
