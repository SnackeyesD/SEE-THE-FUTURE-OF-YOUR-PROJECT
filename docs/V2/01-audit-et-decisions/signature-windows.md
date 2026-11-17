# Signature Windows — dossier ouvert en phase 01

> La signature n'est pas un détail de fin de projet : sans elle, SmartScreen bloque l'installateur et le lancement de janvier est manqué. Ce dossier est ouvert dès la phase 01, même si la signature réelle est appliquée en phase 16.

## 1. Objectif

- Signer **l'exécutable** et **l'installateur** Windows avec un certificat de signature de code reconnu.
- Obtenir un comportement SmartScreen acceptable : au minimum un avertissement standard, pas un blocage « éditeur inconnu ».
- Rendre la vérification possible par l'utilisateur : empreinte, éditeur, horodatage.
- Ne jamais publier un binaire non signé sans procédure de secours explicite.

## 2. Décision à prendre (bloquante)

| Question | Options | Impact |
|---|---|---|
| Entité signataire | Personne morale existante / personne physique | La plupart des AC acceptent les deux, mais les exigences de vérification diffèrent. |
| Type de certificat | **OV** (organisation validée) / **EV** (validation étendue) | EV améliore la réputation SmartScreen plus vite ; OV peut suffire après réputation. |
| Porteur de clé | Token matériel USB / HSM cloud / service de signature | Depuis 2023, les AC n'émettent plus de certificat de signature de code en fichier simple. |
| Service | AC classique (DigiCert, Sectigo, GlobalSign…) / **Azure Trusted Signing** | Azure exige une ancienneté vérifiable de l'organisation (3 ans) et un compte Azure. |
| Build | Local signé / CI signée | La CI doit détenir un accès au token/HSM sans exposer la clé. |

**Recommandation par défaut** : OV sur token matériel via une AC reconnue, avec horodatage RFC 3161. EV si le budget et les délais le permettent et si l'objectif est de réduire immédiatement les avertissements SmartScreen.

## 3. Options et ordres de grandeur

> Les prix et délais sont indicatifs (2026) et doivent être confirmés par devis. Ils servent à décider, pas à contracter.

| Option | Prix indicatif / an | Délai indicatif | Avantages | Contraintes |
|---|---|---|---|---|
| OV standard + token | 250–500 € | 1–3 semaines | Reconnu, moins cher | Vérification d'identité ; réputation SmartScreen à construire |
| EV + token/HSM | 400–900 € | 2–5 semaines | Réputation plus rapide, exigences renforcées | Vérification société/structure, token physique |
| Azure Trusted Signing | ~10 €/mois + usage | 1–3 semaines | Clé dans Azure, CI simple, pas de token à brancher | Éligibilité (ancienneté, historique), compte Azure, dépendance cloud |
| Signature auto-signée | 0 € | immédiat | Tests internes | **Inacceptable pour le public** : SmartScreen bloque |

Coûts annexes : token matériel (50–150 €), horodatage (souvent inclus), éventuel coffre/HSM, temps de vérification juridique.

## 4. Démarche recommandée

### Étape 1 — Cadrage (phase 01)

- [ ] Décider entité signataire et pays de dépôt.
- [ ] Choisir OV ou EV, et AC classique ou Azure Trusted Signing.
- [ ] Vérifier les pièces demandées : registre de commerce, identité, justificatif d'adresse, domaine, téléphone.
- [ ] Nommer un responsable signature (qui détient le token, qui signe la release).

### Étape 2 — Achat et validation (phase 01–02)

- [ ] Demander un devis et un délai ferme.
- [ ] Lancer la vérification d'identité ; répondre aux demandes de l'AC.
- [ ] Recevoir le token/HSM et initialiser le PIN dans un coffre.
- [ ] Documenter la procédure de récupération (que faire si le token est perdu).

### Étape 3 — Intégration (phase 16)

- [ ] Configurer la signature Tauri : empreinte du certificat ou commande de signature (`signtool` / service Azure).
- [ ] Horodater chaque binaire (RFC 3161).
- [ ] Signer l'exécutable **et** l'installateur.
- [ ] Vérifier avec `signtool verify /pa /v` et l'empreinte publiée.
- [ ] Tester sur une **VM Windows propre** : installation, lancement, SmartScreen, désinstallation.
- [ ] Soumettre les faux positifs antivirus (Defender + un moteur en ligne).
- [ ] Publier l'empreinte SHA-256 et la procédure de vérification.

### Étape 4 — Réputation

- [ ] Signer toutes les releases avec le même certificat.
- [ ] Éviter les changements de nom d'éditeur.
- [ ] Surveiller SmartScreen sur plusieurs semaines ; documenter les blocages.
- [ ] Ne jamais réutiliser un certificat compromis ; révocation et communication.

## 5. Plan B si le certificat n'est pas prêt

Le plan B ne doit **jamais** être présenté comme équivalent à une signature.

1. **Livraison interne / beta** : binaire non signé, avertissement explicite, empreinte SHA-256 publiée, canal de support.
2. **Signature standard (OV) sans EV** : si l'EV est bloquée, signer en OV ; SmartScreen peut afficher un avertissement, mais l'éditeur est identifié.
3. **Installateur alternatif** : archive ZIP portable avec vérification d'empreinte, en attendant l'installateur signé.
4. **Communication** : page « Pourquoi Windows affiche un avertissement » avec la procédure de vérification.
5. **Interdiction** : pas de certificat auto-signé pour le public, pas de contournement SmartScreen demandé à l'utilisateur, pas de binaire non signé présenté comme signé.

## 6. Ce qu'il faut préparer maintenant

| Élément | Responsable | Échéance |
|---|---|---|
| Décision entité / type de certificat | Produit + direction | Phase 01 |
| Devis et délai ferme | Admin/finance | Phase 01 |
| Vérification d'identité | Direction | Phase 01–02 |
| Token/HSM et coffre | Infra | Phase 02 |
| Procédure de signature CI | Infra | Phase 16 |
| VM Windows propre de test | QA | Phase 16 |
| Page de vérification d'empreinte | Produit | Phase 16 |

## 7. Risques

| Risque | Impact | Mitigation |
|---|---|---|
| Vérification d'identité refusée ou lente | Lancement bloqué | Lancer en phase 01, préparer les pièces, avoir un plan B OV |
| Token perdu ou PIN oublié | Impossible de signer | Coffre, double responsable, procédure de réémission |
| SmartScreen continue de bloquer | Adoption freinée | EV, signature constante, réputation, page explicative |
| Antivirus faux positif | Installation impossible | Soumission, signature, tests VM propre |
| Azure Trusted Signing non éligible | Retard | Alternative AC classique |
| Clé exposée en CI | Compromission | Token/HSM, secrets, accès restreint, audit |

## 8. Décision de phase 01 — tranchée le 2026-11-17

- [x] Type de certificat retenu : **OV** sur token matériel USB, avec horodatage RFC 3161. EV reste une option si le budget le permet et si la réputation SmartScreen au lancement est critique ; **Azure Trusted Signing écarté** (éligibilité : 3 ans d'ancienneté vérifiable + compte Azure, dépendance cloud pour la CI).
- [x] AC retenue et devis : **AC classique reconnue (DigiCert, Sectigo ou GlobalSign)** — devis avec délai ferme à demander en phase 01 (ordre de grandeur 250–500 €/an, 1–3 semaines).
- [ ] Responsable signature nommé : **à nommer par la direction d'ici la fin de la phase 01**, avec un suppléant ; token conservé au coffre, procédure de réémission documentée.
- [x] Plan B validé si le certificat arrive après la phase 16 : **OV** ; sinon archive ZIP portable + empreinte SHA-256 publiée (beta interne uniquement). Jamais de binaire public non signé, jamais de certificat auto-signé pour le public.
- [x] Vérification d'identité lancée en phase 01–02 (pièces prêtes : registre de commerce, pièce d'identité, justificatif d'adresse, domaine, téléphone), même si la signature n'est appliquée qu'en phase 16.

Décision consignée dans [`decisions-lancement.md`](decisions-lancement.md) (D4).

> Ce document est un dossier de travail, pas un avis juridique. Les exigences des AC et de Microsoft évoluent ; vérifier les conditions au moment de l'achat.
