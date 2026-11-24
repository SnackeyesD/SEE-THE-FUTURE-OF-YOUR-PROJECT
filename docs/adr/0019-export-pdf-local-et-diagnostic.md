# ADR 0019 — Export PDF local et diagnostic sans télémétrie

- **Statut** : accepté
- **Date** : 2026-11-24
- **Contexte** : phase 16, complète l'ADR 0018

## Décision

### Le PDF est un rendu du même Markdown

Le PDF n'est pas un second calculateur. `build_pdf(report)` appelle d'abord
`build_markdown(report)`, puis met en page ce texte. Les deux exports partagent
donc la même source, les mêmes unités et les mêmes chiffres. Un test vérifie
que chaque appel produit exactement les mêmes octets et que le PDF contient les
sections attendues.

Conséquences :

- aucune valeur n'est recalculée dans le renderer ;
- une correction de formulation se fait une seule fois, dans le Markdown ;
- les limites connues du Markdown (tableaux larges) restent visibles dans le
  PDF plutôt que masquées par une seconde logique.

### Un générateur PDF minimal, sans dépendance

Le module `see_reporting.pdf` écrit un PDF 1.4 avec les polices standard
Helvetica en encodage WinAnsi. Il n'embarque pas de police, n'appelle aucun
service et n'ajoute aucune dépendance au paquet `reporting`. Les métadonnées
sont fixes (titre, auteur, créateur), sans date de création ni chemin local :
deux exports identiques restent identiques.

Le PDF est transmis en base64 par JSON-RPC. Le sidecar reste seul producteur
des octets ; l'interface ne fait que les télécharger. Le protocole passe en
`1.16.0` avec `report.buildPdf` et `ReportPdfResult`.

### Le diagnostic est local, borné et nettoyé

Le bouton « Exporter le diagnostic » construit un JSON côté interface à partir
de :

- la version de l'application, la langue et l'agent utilisateur ;
- l'état du sidecar et les versions de protocole ;
- les 50 derniers événements du journal ;
- au plus 10 entrées du journal local d'erreurs, si activé.

Avant écriture, `scrubDiagnosticText` masque les clés (`sk-`, `AIza`, `ghp_`,
`xox…`), les affectations `api_key=`, les jetons `Bearer`, les chemins Windows,
UNC et POSIX courants, les courriels et les noms de projets du projet courant.

Aucun envoi réseau n'est implémenté. Le fichier produit reste sous le contrôle
de l'utilisateur, qui peut le relire avant de le partager.

### Le journal d'erreurs est opt-in et silencieux

`installCrashLogger` écoute `error` et `unhandledrejection`, mais
`recordCrash` ne fait rien tant que l'utilisateur n'a pas activé l'option. Les
messages sont nettoyés, tronqués à 500 caractères et limités à 10 entrées. La
désactivation efface immédiatement le journal. Aucune infrastructure de collecte
n'existe dans la version `3.0.0`.

### Les textes légaux sont provisoires et dans le dépôt

`docs/legal/POLITIQUE-CONFIDENTIALITE.md` et `docs/legal/CGU.md` décrivent le
comportement réel du logiciel. Ils sont marqués provisoires jusqu'à validation
juridique. L'écran « À propos » en reprend l'essentiel pour que l'utilisateur
n'ait pas à ouvrir le dépôt.

## Alternatives écartées

- **Convertir le PDF via une bibliothèque lourde** (WeasyPrint, Playwright) :
  ajout de dépendances système, taille d'installeur et surface de sécurité
  injustifiés pour un document textuel.
- **Imprimer la webview** : dépend du moteur de rendu de la plateforme, difficile
  à tester et à rendre déterministe.
- **Envoyer automatiquement les crashs** : contraire au local-first et à la
  promesse de l'ADR 0016 ; aucun consentement explicite ne serait recueilli.
- **Stocker un journal d'erreurs complet** : risque de fuite de chemins ou de
  noms de projets, et rétention non maîtrisée.

## Vérifications

- `packages/reporting/tests/test_pdf.py` : déterminisme, structure, accents,
  absence de chemins et de secrets.
- `sidecar/tests/test_report_service.py` : build PDF, refus d'un run absent,
  nom de fichier, base64 et longueur.
- `apps/desktop/src/lib/diagnostic.test.ts` et `crashlog.test.ts` : masquage,
  borne, opt-in, désactivation.
- `ResultsScreen.test.tsx` : les deux boutons d'export déclenchent la bonne
  action.
