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

## Reste à faire
- [ ] Recette continue sur machine réelle : confirmer les autres mappings (état 2.2, défaut 2.3, programme 2.4, énergie, eau, progression…)
- [ ] Fabien observe les capteurs `Propriété x.y` pendant un cycle complet → diff → mapping JSON complet
- [ ] **SYNCHRONISATION RETOUR FORGE** : le commit `6b6fca9` (URLs HACS → GitHub) n'existe que sur GitHub. Sur le serveur (forge) : `git fetch https://github.com/fs83500/dreame_laundry.git main && git merge --ff-only FETCH_HEAD && git push origin main` (fast-forward depuis 2903a4e, aucun conflit). Codex ne peut pas pousser sur git.dpnac.cloud (pas de credentials Forgejo dans son sandbox).
- [ ] **DESCRIPTION + TOPICS GitHub (valeurs proposées, prêtes à coller)** — métadonnées hors git, à renseigner dans l'UI GitHub (⚙️ section About) ou via l'API avec un PAT ; aucun agent n'a d'écriture API GitHub (module git_push = transport git uniquement).
  - Description FR : « Intégration Home Assistant pour lave-linge et sèche-linge Dreame via le cloud Dreamehome (état, programme, temps restant, consommation) »
  - Description EN (recommandée pour HACS/international) : « Home Assistant integration for Dreame washing machines and dryers via the Dreamehome cloud (state, program, remaining time, energy) »
  - Topics : `home-assistant`, `hacs`, `dreame`, `laundry`, `washing-machine`, `clothes-dryer`, `custom-integration`
  - NOTE : requis seulement pour le store HACS par défaut — un dépôt personnalisé HACS fonctionne sans ; la CI les ignore déjà (`ignore: brands description topics`).
- [ ] Sur GitHub : renseigner la description et les topics du dépôt (vérifiés par HACS, ignorés dans la CI en attendant)
- [ ] Optionnel : miroir automatique forge → GitHub à chaque release (l'installation via HACS impose GitHub)

## Décisions
- HACS ne supporte que GitHub (code source vérifié) : la forge Forgejo ne peut PAS être un dépôt personnalisé HACS. Installation manuelle = référence.
- Le code vendored `cloud/protocol.py` (Tasshack, MIT) n'est ni reformaté ni linté — on n'y touche pas pour faciliter les mises à jour amont
- Mapping par défaut scindé : washer (2.11 confirmé) ≠ dryer (2.5 guess) — ne pas généraliser une découverte d'un modèle à l'autre
- Version 0.1.2, archives zip versionnées livrées à la racine du dépôt

## Correspondance propriétés découverte (lave-linge Fabien, 31/10/2026)
- `2.11` = temps restant (minutes) — confirmé par observation (décroît pendant le cycle)

## Journal de terrain
- **01/11/2026 09:12** — retour de terrain : 8× `Error while executing request: Read timed out. (timeout=6)` en ~1 min (`cloud/protocol.py:1403`, WARNING). Diagnostic : timeout de lecture HTTP (6 s, 2 réessais) quand la machine est éteinte/Wi-Fi coupé — flux poll 30 s + keep-awake 60 s. Comportement prévu (UpdateFailed → dernières valeurs conservées, capteur Joignable → Non). Pas un bug ; vendored inchangé (décision projet). Section « Dépannage » ajoutée au README (explication + recette `logger:` pour masquer le bruit).