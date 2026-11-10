# Audit d'actionnabilité des messages — principe Snyk appliqué

> Principe (Snyk, developer-centric) : *« donner aux utilisateurs des messages qui disent exactement ce qui ne va pas et ce qu'ils doivent faire »*. Un message qui ne guide pas vaut moins que la moitié d'un message.

---

## 1. Le bon côté (à préserver et généraliser)

Les états vides sont déjà **bonnes** — chaque `EmptyState` dit où on est, quoi faire, et propose souvent une action :

| Écran | Message | Verdict |
|---|---|---|
| Projects | « Bienvenue dans See The Future — Transformez une idée en scénario chiffré, sans inventer de chiffres. » | ✅ Actionnable + rassure |
| Projects | « Aucun projet pour l'instant — Créez un projet ci-dessous pour démarrer. » | ✅ |
| Interview | « Commencez par votre idée — Pas besoin d'un business plan. Une phrase suffit. » | ✅ |
| Simulation | « Hypothèses requises — Enregistrez d'abord un scénario avec au moins une hypothèse. » | ✅ Séquencé |
| Results | « Aucun résultat à afficher — Lancez une simulation pour obtenir les graphiques. » | ✅ |

Les `InlineAlert` avec **titre** portent du sens : « Vos clés restent chez vous », « Champs requis manquants », « Chiffres non reconnus », « Cohérence vérifiée » — le produit assume sa promesse, c'est bien.

## 2. Le problème principal : erreurs = exceptions brutes

**9 des 13 affichages d'erreur** montrent `String(reason)` — c'est-à-dire le texte d'une exception technique, sans titre, sans contexte, sans action :

| Localisation | Appel | Ce que voit l'utilisateur |
|---|---|---|
| `ProvidersPanel.tsx` ×9 | `setError(String(reason))` (l.188, 233, 261, 278, 292, 318, 331, 352, 400) | ex. « Error: request failed: …JSON… » |
| `BriefScreen.tsx` l.155 | `{error}` sans titre | dépend du message IPC |
| `HypothesesScreen.tsx` l.256 | `{message}` sans titre | idem |
| `InterviewScreen.tsx` l.122 | `{error}` sans titre | idem |
| `ProjectsScreen.tsx` l.51 | `{error}` sans titre | idem |
| `ResultsScreen.tsx` l.81 | `{error}` sans titre | idem |
| `SimulationScreen.tsx` l.68 | `{error}` sans titre | idem |

En plus, les erreurs passent par `pushLog("error", humanize(reason))` dans `App.tsx` (6 occurrences) — la liste de logs est un bon filet, mais ne remplace pas le message en surface.

### Ce qu'exige le principe Snyk

Un message d'erreur doit répondre à 3 questions : **qu'est-ce qui a échoué ? pourquoi (langage humain) ? quoi faire maintenant ?** Format cible pour la phase 03 (composant `Alert`) :

```
tone: "danger"
title: "La simulation n'a pas pu démarrer"        ← quoi (nommé)
body: "Le moteur n'a pas répondu dans les 30 s."  ← pourquoi (humain, pas la stack)
action: { label: "Relancer", onClick }            ← quoi faire
+ détail technique repliable (pour le diagnostic)
```

## 3. Autres messages non actionnables relevés

| Fichier | Ligne | Message | Problème |
|---|---|---|---|
| `ProvidersPanel.tsx` | 410 | « Disponible uniquement dans l'application Tauri. » | Dit une limite, pas la solution (ouvrir l'app desktop). Fait aussi état d'un `card--wide` legacy |
| `ResultsScreen.tsx` | 179 | « L'agent prépare la narration… » | OK mais état muet si > 30 s : prévoir réassurance/action |
| `InterviewScreen.tsx` | 114 | « Aucun fournisseur associé » + body | Vérifier que le body dit **où configurer** (écran Settings) — bien sinon |
| `Charts.tsx` | 26/109/168 | « Aucune distribution/sensibilité/projection disponible. » | Dits qu'il n'y a rien, pas pourquoi ni quoi faire (réexécuter ? vérifier la graine ?) |
| `HypothesesScreen.tsx` | 287 | « unité · requis » | Marqueur discret : à renforcer visuellement (badge) pour la lisibilité |
| `SettingsScreen.tsx` | 260 | « Aucun événement. » (logs) | Acceptable pour une liste de logs |

## 4. Recommandations portées aux phases suivantes

1. **Phase 03** : le composant `Alert` exige `title` + `action?` ; les champs d'erreur passent par `Field.error` avec message humain.
2. **Phase 05** : transformer chaque `setError(String(reason))` en message nommé — l'IPC fournit déjà des erreurs typées côté sidecar (`packages/engine/errors.py`, `storage/errors.py`) : les mapper vers des libellés humains, pas `String()`.
3. **Phase 05** : les trois charts (« Aucune … disponible ») adoptent `Empty` avec cause probable + action.
4. **Phase 06** : l'état « erreur » doit rester lisible si la couleur est ignorée (icône/label, cf. WCAG 1.4.1).
