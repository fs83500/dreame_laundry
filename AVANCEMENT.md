# Avancement — dreame_laundry

## Contexte
Intégration Home Assistant pour lave-linge / sèche-linge Dreame via le cloud Dreamehome.
Dépôt : https://git.dpnac.cloud/fabien.solvez/dreame (forge Forgejo de Fabien).

## Fait
- [x] Analyse complète du zip d'origine (architecture, sécurité, traductions, tests, lint)
- [x] Restructuration dépôt : `hacs.json` + `README.md` + `pytest.ini` + `tests/` à la racine, intégration dans `custom_components/dreame_laundry/`
- [x] Manifest : forge git.dpnac.cloud, codeowners `@fabien.solvez`, `cryptography>=42.0.0` ajouté aux requirements
- [x] Qualité : ruff check + format OK (hors `cloud/` vendored Tasshack, MIT), compilation Python OK, JSON valides
- [x] Push sur main : 24fb029 (v0.1.1) → f986b0e (URLs forge) → 526f687 (zip) → 2f0b571 (mapping 2.11)
- [x] HACS ne supporte que GitHub → installation manuelle validée sur l'installation réelle (HA 2026.7.2)
- [x] v0.1.2 : `remaining_time` lave-linge = `2.11` CONFIRMÉ (avant le guess 2.5, faux sur machine réelle) — dryer garde 2.5 (non vérifié)
- [x] Archive d'installation `dreame_laundry-0.1.2.zip` (24 fichiers, custom_components uniquement) + sha256 4f8eacdf…

## Reste à faire
- [ ] Recette continue sur machine réelle : confirmer les autres mappings (état 2.2, défaut 2.3, programme 2.4, énergie, eau, progression…)
- [ ] Fabien observe les capteurs `Propriété x.y` pendant un cycle complet → diff → mapping JSON complet
- [ ] Optionnel : miroir push forge → GitHub si l'installation via HACS est souhaitée

## Décisions
- HACS ne supporte que GitHub (code source vérifié) : la forge Forgejo ne peut PAS être un dépôt personnalisé HACS. Installation manuelle = référence.
- Le code vendored `cloud/protocol.py` (Tasshack, MIT) n'est ni reformaté ni linté — on n'y touche pas pour faciliter les mises à jour amont
- Mapping par défaut scindé : washer (2.11 confirmé) ≠ dryer (2.5 guess) — ne pas généraliser une découverte d'un modèle à l'autre
- Version 0.1.2, archives zip versionnées livrées à la racine du dépôt

## Correspondance propriétés découverte (lave-linge Fabien, 31/10/2026)
- `2.11` = temps restant (minutes) — confirmé par observation (décroît pendant le cycle)