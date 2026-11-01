# Avancement — dreame_laundry

## Contexte
Intégration Home Assistant pour lave-linge / sèche-linge Dreame via le cloud Dreamehome.
Dépôt : https://git.dpnac.cloud/fabien.solvez/dreame (forge Forgejo de Fabien).

## Fait
- [x] Analyse complète du zip d'origine (architecture, sécurité, traductions, tests, lint)
- [x] Restructuration dépôt : `hacs.json` + `README.md` + `pytest.ini` + `tests/` à la racine, intégration dans `custom_components/dreame_laundry/`
- [x] Manifest : forge git.dpnac.cloud, codeowners `@fabien.solvez` (`cryptography` retiré en v0.1.3 : déjà fourni par HA, refusé par hassfest)
- [x] Qualité : ruff check + format OK (hors `cloud/` vendored Tasshack, MIT), compilation Python OK, JSON valides
- [x] Push sur main : 24fb029 (v0.1.1) → f986b0e (URLs forge) → 526f687 (zip) → 2f0b571 (mapping 2.11)
- [x] HACS ne supporte que GitHub → installation manuelle validée sur l'installation réelle (HA 2026.7.2)
- [x] v0.1.2 : `remaining_time` lave-linge = `2.11` CONFIRMÉ (avant le guess 2.5, faux sur machine réelle) — dryer garde 2.5 (non vérifié)
- [x] Archive d'installation `dreame_laundry-0.1.2.zip` (24 fichiers, custom_components uniquement) + sha256 4f8eacdf…
- [x] **Publication GitHub (01/11/2026 01:55)** : miroir public [fs83500/dreame_laundry](https://github.com/fs83500/dreame_laundry) publié depuis la forge (fusion `-s ours` du stub initial GitHub, push fast-forward 1cc5be8) ; README installation HACS → URL GitHub, manifest documentation → GitHub, codeowners `@fs83500`
- [x] **v0.1.3 — compatibilité Home Assistant / HACS (01/11/2026)** : `manifest.json` + `issue_tracker` (exigé par HACS) ; `hacs.json` version minimale HA 2025.2.0 (`AddConfigEntryEntitiesCallback`) ; icônes déplacées dans `icons.json` (pratique HA actuelle) ; test d'intégration corrigé (temps restant lave-linge = 2.11) ; CI GitHub `.github/workflows/validate.yml` (hassfest, validation HACS, ruff + pytest) ; testé sur HA 2026.2.3 (7/7 tests OK) ; archive `dreame_laundry-0.1.3.zip`

- [x] **v0.1.4 (01/11/2026)** — fix du **bruit de timeouts à l'initialisation** (retour de terrain : 8× `Read timed out (timeout=6)` à ~09:12, uniquement au démarrage). Cause : le premier poll tourne sur une session TLS fraîche ET interroge toutes les propriétés découvertes (`_poll_count=0` → raw inclus), dépassant le timeout de lecture vendored (6 s) → burst de warnings, puis plus rien une fois la session chaude. Fix (sans toucher le vendored) : `coordinator._sync_update` passe `timeout=15` au premier poll, défaut ensuite ; `api.get_props(codes, timeout=None)` transmet le paramètre à `send()` (plomberie déjà présente dans le vendored). Tests : timeout transmis (test_api) + premier poll 15 s / défaut ensuite (test_integration). Manifest 0.1.4, archive `dreame_laundry-0.1.4.zip` sha256 `80914cdf…`. Le comportement machine-éteinte reste inchangé (capteur Joignable, UpdateFailed) — voir Dépannage README.
- [x] **SYSTÈME DE MISE À JOUR (01/11/2026)** — workflow `.github/workflows/release.yml` (workflow_dispatch : saisit la version, vérifie la cohérence avec `manifest.json`, tagge `vX.Y.Z`, crée la release GitHub avec archive + sha256 en assets). README : section « Mises à jour » (HACS, manuel, processus mainteneur). AVANCEMENT : procédure de release. NOTE INFRA : la forge git.dpnac.cloud/fabien.solvez/dreame est devenue **privée** (401 sur git-upload-pack, absente de la recherche publique, 01/11 ~10h) — plus de fetch possible depuis le sandbox ; GitHub est désormais la source publique de référence, la forge reste le dépôt de développement de Fabien (accès authentifié chez lui).
- [x] **v0.1.5 — corrections (01/11/2026)** : `offset` du mapping appliqué même sans `scale` (et validé comme nombre) ; « Fin prévue » calculée dès le démarrage (avant : inconnue jusqu'au poll suivant) ; identifiants refusés lors d'une écriture ou d'un scan → ré-authentification proposée + erreur HA propre (avant : exception brute, et plantage silencieux du maintien en éveil) ; README Dépannage : niveau logger `error` (la recette `debug` augmentait le bruit au lieu de le réduire) ; workflow Release : saisies passées par variables d'environnement (injection shell), version validée `X.Y.Z`, relançable si la release existe, étape de nettoyage `test-tag-push` retirée ; 11/11 tests OK ; manifest : `categories: ["appliances_cleaning.laundry"]` (supprime l'avertissement HACS « no categories »)
- [x] **v0.1.6 (01/11/2026)** : appareil éteint au démarrage de HA → l'intégration se charge quand même (appareil « non joignable », valeurs revenues au poll suivant) ; avant, tout le setup échouait en boucle avec « Dreamehome cloud unreachable ». Une vraie panne de connexion/login au cloud reste une erreur de setup (nouvel essai). Icône de l'intégration : `custom_components/dreame_laundry/brand/icon.png` (+ `@2x`), source `assets/icon.svg` ; contrôle HACS `brands` réactivé dans la CI. 13/13 tests OK
- [x] **v0.1.7 (01/11/2026)** : **lave-linge** — état = phase `2.4` (Lavage/Rinçage/Essorage/Terminé/Arrêt), « Cycle en cours » basé sur la phase (avant : allumé à tort à l'arrêt car `2.11` y vaut la durée du programme), programme/défaut supposés retirés. **Sèche-linge** — mapping par défaut corrigé d'après le relevé terrain — état `2.1` (1 = Arrêt, 3 = En cours, détermine « Cycle en cours »), programme `2.3`, temps restant `2.11`, plus de « défaut » supposé. Avant : « Défaut » affichait le programme, « Programme » l'état, et le temps restant lisait un paramètre (1/2) → « Cycle en cours » faux. 15/15 tests OK
- [x] **v0.1.8 (01/11/2026)** : appareils nommés d'après le type et le modèle — « Lave-linge L9 » / « Sèche-linge L9 » (traduits, `L9` extrait de `dreame.washer.l9nacn`) au lieu du surnom Dreamehome ; fiche appareil : modèle `L9`, identifiant de modèle `dreame.*.l9nacn`. Entités : « Lave-linge L9 État », `sensor.lave_linge_l9_etat`… (nouvelles installations ; sur une installation existante les ID d'entité restent, voir README). 16/16 tests OK

## Reste à faire
- [ ] Recette continue sur machine réelle : programme (lave-linge), défaut, énergie, eau, progression ; confirmer 2.4 = 1 « Lavage » ; identifier 2.12 / 2.16
- [ ] Fabien observe les capteurs `Propriété x.y` pendant un cycle complet → diff → mapping JSON complet
- [ ] **PROCÉDURE DE RELEASE (système en place, 01/11)** — pour publier une version :
  1. modifier le code + `custom_components/dreame_laundry/manifest.json` (`"version": "X.Y.Z"`) + AVANCEMENT.md, committer sur main (CI doit être verte : hassfest + HACS + tests) ;
  2. GitHub → onglet **Actions** → workflow **Release** → *Run workflow* → branche main, version = X.Y.Z (+ note courte) ;
  3. le workflow vérifie la cohérence manifest/saisie, tagge `vX.Y.Z`, crée la release avec `dreame_laundry-X.Y.Z.zip` + sha256 en assets (relançable : si la release existe, seules les archives sont remplacées) ;
  4. HACS proposera la mise à jour aux installations ; l'archive sert à l'installation manuelle.
- [ ] **SYNCHRONISATION RETOUR FORGE** : la forge est passée en **privée** (01/11, 401 sur git-upload-pack, absente de la recherche publique) — plus de fetch anonyme possible depuis le sandbox. Fabien, chez toi : `git fetch https://github.com/fs83500/dreame_laundry.git main && git merge --ff-only FETCH_HEAD && git push origin main` (fast-forward depuis 2903a4e). Désormais **GitHub = source publique de référence**, forge = développement.
- [ ] **DESCRIPTION + TOPICS GitHub (valeurs proposées, prêtes à coller)** — métadonnées hors git, à renseigner dans l'UI GitHub (⚙️ section About) ou via l'API avec un PAT ; aucun agent n'a d'écriture API GitHub (module git_push = transport git uniquement).
  - Description FR : « Intégration Home Assistant pour lave-linge et sèche-linge Dreame via le cloud Dreamehome (état, programme, temps restant, consommation) »
  - Description EN (recommandée pour HACS/international) : « Home Assistant integration for Dreame washing machines and dryers via the Dreamehome cloud (state, program, remaining time, energy) »
  - Topics : `home-assistant`, `hacs`, `dreame`, `laundry`, `washing-machine`, `clothes-dryer`, `custom-integration`
  - NOTE : requis seulement pour le store HACS par défaut — un dépôt personnalisé HACS fonctionne sans ; la CI les ignore déjà (`ignore: brands description topics`).
- [ ] Optionnel : miroir automatique forge → GitHub à chaque release (l'installation via HACS impose GitHub)

## Décisions
- HACS ne supporte que GitHub (code source vérifié) : la forge Forgejo ne peut PAS être un dépôt personnalisé HACS. Installation manuelle = référence.
- Le code vendored `cloud/protocol.py` (Tasshack, MIT) n'est ni reformaté ni linté — on n'y touche pas pour faciliter les mises à jour amont
- Mapping par défaut scindé washer / dryer, chacun d'après son propre relevé — ne pas généraliser une découverte d'un modèle à l'autre
- Version 0.1.2, archives zip versionnées livrées à la racine du dépôt

## Correspondance propriétés découverte (lave-linge Fabien, 31/10/2026)
- `2.11` = temps restant (minutes) — confirmé par observation (décroît pendant le cycle)
- `1.4` = version du firmware — relevée par Fabien le 01/11/2026 (capteur « Propriété 1.4 »). Conforme au service MIoT standard « device information » (siid 1), où `1.1` = fabricant, `1.2` = modèle, `1.3` = n° de série, `1.4` = firmware.

### Scan complet lave-linge `dreame.washer.l9nacn` (« Moumouss »), 01/11/2026, pendant la **phase LAVAGE** (2.11 = 47 min restantes) — scan pendant le rinçage à venir
29 propriétés répondent :

| siid.piid | valeur | hypothèse (à confirmer par un 2ᵉ scan à l'arrêt) |
|---|---|---|
| 1.4 | `"0.1.1_3017"` | **firmware (confirmé)** |
| 1.5 | `"12345678"` | valeur factice (n° de série non renseigné ?) |
| 2.1 | 3 | **candidat « état / phase »** (≠ 0 pendant le cycle ; 3 = lavage ?) |
| 2.2 | 0 | ⚠️ mapping par défaut « état » — vaut 0 en plein cycle : probablement faux |
| 2.3 | 0 | défaut (0 = aucun) plausible |
| 2.4 | 1 | programme ? |
| 2.5 | 0 | — |
| 2.8 | 3 | niveau (température / essorage / saleté ?) |
| 2.11 | 47 | **temps restant (confirmé)** |
| 2.12 | 87 | durée totale du cycle (min) ? → progression ≈ (87−47)/87 |
| 2.13 | 47 | = 2.11 : temps restant affiché / fin différée ? |
| 2.14, 2.15, 2.19 | 0 | — |
| 2.16 | 1 | option activée (booléen ?) |
| 2.18, 2.24, 2.25 | 4 | réglages (niveaux) ? |
| 3.4–3.9, 3.13, 3.14 | 0 / 3.7 = 1 | service 3 : options / dosage ? |
| 4.6, 4.7 | 0 | — |
| 5.1 | 0 | — |

Prochaine étape : un scan **machine allumée à l'arrêt** (et si possible à une autre phase du cycle) pour comparer — ce qui change entre les deux identifie état, phase et programme.

### Synthèse lave-linge `dreame.washer.l9nacn` (« Moumouss »), 01/11/2026 — plusieurs scans (lavage, rinçage, essorage, fin, arrêt)
Remplace les hypothèses du premier scan ci-dessus.

| siid.piid | valeur | signification | statut |
|---|---|---|---|
| 2.1 | 2 | machine à l'arrêt | confirmé |
| 2.1 | 3 | cycle actif ou terminé | observé |
| **2.4** | 1 | **Lavage** | probable |
| **2.4** | 2 | **Rinçage** | confirmé |
| **2.4** | 3 | **Essorage** | confirmé |
| **2.4** | 6 | **Terminé** | confirmé |
| **2.4** | 8 | **Arrêt** | confirmé |
| **2.11** | variable | **temps restant (min)** ; à l'arrêt = durée du programme sélectionné (97) | confirmé |
| 2.13 | variable | identique à 2.11 | très probable |
| 2.12 | 87 / 0 | lié au fonctionnement (87 en cycle, 0 à l'arrêt) | à identifier |
| 2.16 | 0 / 1 | lié aux phases du cycle | à identifier |
| 3.6 | 0 / 1 | rafraîchissement de l'air désactivé / activé | probable |
| 3.14 | 0 / 1 | autorisation sur le réseau désactivée / activée | confirmé |

Inconnues (valeur constante sur les scans) : 1.5 (`12345678`), 2.2, 2.3, 2.5, 2.8 (3), 2.14, 2.15, 2.18 (4), 2.19, 2.24 (4), 2.25 (4), 3.4, 3.5, 3.7 (1), 3.8, 3.9, 3.13, 4.6, 4.7, 5.1. Firmware 1.4 = `0.1.1_3017`.

→ **Mapping par défaut v0.1.7** : état = `2.4` (libellés ci-dessus, « Cycle en cours » = 1/2/3), temps restant = `2.11`. Programme et défaut retirés (non identifiés ; l'ancien « programme » 2.4 était la phase, l'ancien « état » 2.2 restait à 0).

### Relevé sèche-linge `dreame.dryer.l9nacn`, 01/11/2026 (Fabien) — 23 propriétés
| siid.piid | fonction | valeurs observées | statut |
|---|---|---|---|
| 1.4 | version firmware | `V3029.20260709.D` | probable |
| 1.5 | identifiant interne | `12345678` | inconnu (factice, comme sur le lave-linge) |
| 2.1 | **état** | 1 = arrêt, 3 = en cours | probable → **mapping par défaut v0.1.7** |
| 2.2 | ? | 0 | à identifier (ancien défaut « état » : faux) |
| 2.3 | **programme** | 0, 1, 4, 5, 6, 21, 22 | **confirmé** → mapping par défaut v0.1.7 (ancien défaut « défaut » : faux) |
| 2.4 | état / phase du cycle | 3 = en cours, 4 = arrêt | probable (ancien défaut « programme » : faux) |
| 2.5 | paramètre du programme | 1, 2 | à identifier (ancien défaut « temps restant » : faux) |
| 2.6 | option / niveau de séchage | 0, 1, 2 | à identifier |
| 2.9 | durée initiale du cycle | 0, 112 | probable |
| 2.10, 2.12 | ? | 0 | à identifier |
| 2.11 | **temps restant** | 17 à 120 min | probable → mapping par défaut v0.1.7 |
| 2.13 | option / indicateur | 0, 1 | à identifier |
| 3.2 | ? | 1 | à identifier |
| 3.3, 3.4, 3.5, 3.10, 3.12, 3.13, 3.14 | ? | 0 | à identifier |
| 3.8 | antifroissage | 0 = désactivé, 1 = activé | confirmé (capteur brut « Propriété 3.8 ») |
| 4.6 | ? | 0 | à identifier |

## Journal de terrain
- **01/11/2026 09:12** — retour de terrain : 8× `Error while executing request: Read timed out. (timeout=6)` en ~1 min (`cloud/protocol.py:1403`, WARNING). Diagnostic : timeout de lecture HTTP (6 s, 2 réessais) quand la machine est éteinte/Wi-Fi coupé — flux poll 30 s + keep-awake 60 s. Comportement prévu (UpdateFailed → dernières valeurs conservées, capteur Joignable → Non). Pas un bug ; vendored inchangé (décision projet). Section « Dépannage » ajoutée au README (explication + recette `logger:` pour masquer le bruit).