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

## Reste à faire
- [ ] Recette continue sur machine réelle : confirmer les autres mappings (état 2.2, défaut 2.3, programme 2.4, énergie, eau, progression…)
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
- Mapping par défaut scindé : washer (2.11 confirmé) ≠ dryer (2.5 guess) — ne pas généraliser une découverte d'un modèle à l'autre
- Version 0.1.2, archives zip versionnées livrées à la racine du dépôt

## Correspondance propriétés découverte (lave-linge Fabien, 31/10/2026)
- `2.11` = temps restant (minutes) — confirmé par observation (décroît pendant le cycle)
- `1.4` = version du firmware — relevée par Fabien le 01/11/2026 (capteur « Propriété 1.4 »). Conforme au service MIoT standard « device information » (siid 1), où `1.1` = fabricant, `1.2` = modèle, `1.3` = n° de série, `1.4` = firmware.

## Journal de terrain
- **01/11/2026 09:12** — retour de terrain : 8× `Error while executing request: Read timed out. (timeout=6)` en ~1 min (`cloud/protocol.py:1403`, WARNING). Diagnostic : timeout de lecture HTTP (6 s, 2 réessais) quand la machine est éteinte/Wi-Fi coupé — flux poll 30 s + keep-awake 60 s. Comportement prévu (UpdateFailed → dernières valeurs conservées, capteur Joignable → Non). Pas un bug ; vendored inchangé (décision projet). Section « Dépannage » ajoutée au README (explication + recette `logger:` pour masquer le bruit).