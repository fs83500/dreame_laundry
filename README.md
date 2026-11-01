# Dreame Laundry pour Home Assistant

Intégration personnalisée pour les lave-linge et sèche-linge Dreame appairés dans l'appli **Dreamehome** : état, programme, temps restant, consommation, et maintien en éveil.

Elle passe par le cloud Dreamehome (HTTP pour lire/écrire, MQTT pour les changements en temps réel). Le client cloud est repris de [Tasshack/dreame-vacuum](https://github.com/Tasshack/dreame-vacuum) (licence MIT, voir `cloud/LICENSE.tasshack`).

> **Dépôts** : développement sur la forge [git.dpnac.cloud/fabien.solvez/dreame](https://git.dpnac.cloud/fabien.solvez/dreame) — miroir public [GitHub fs83500/dreame_laundry](https://github.com/fs83500/dreame_laundry) (requis pour HACS, qui n'accepte que GitHub).

## Installation

Prérequis : Home Assistant **2025.2** ou plus récent.

### Via HACS (recommandé)

1. HACS → *⋮ (en haut à droite) → Dépôts personnalisés*.
2. URL : `https://github.com/fs83500/dreame_laundry`, catégorie : **Intégration**.
3. Le dépôt apparaît → **Télécharger**.
4. Redémarre Home Assistant.
5. *Paramètres → Appareils et services → Ajouter une intégration → Dreame Laundry*.
6. Identifiants Dreamehome + région du compte (Europe par défaut), puis coche les deux appareils.

### Manuellement

1. Copie `custom_components/dreame_laundry` dans `/config/custom_components/`.
2. Redémarre Home Assistant, puis comme ci-dessus (étapes 5-6).

## Première étape obligatoire : le scan des propriétés

Dreame ne publie pas la liste des propriétés (siid/piid) de ses lave-linge et sèche-linge. Au départ, quelques correspondances **supposées** existent (état `2.2`, défaut `2.3`, programme `2.4`) ; elles portent l'attribut `mapping: guess`. Le temps restant `2.11` est **confirmé** sur lave-linge (vérifié le 31/10/2026) ; sur sèche-linge il reste supposé (`2.5`).

1. Appareil allumé, appuie sur **Scanner les propriétés** (entité de diagnostic). Une notification liste toutes les propriétés qui répondent, et chacune devient un capteur `Propriété x.y`.
2. Lance un cycle et regarde quels capteurs `Propriété x.y` bougent : temps restant qui décroît, état qui change, compteur d'énergie qui monte.
3. Déclare ce que tu as trouvé dans *Options* de l'intégration (champ JSON).

Exemple :

```json
{
  "washer": {
    "status": {"prop": "2.2", "map": {"1": "Veille", "2": "Lavage", "3": "Rinçage", "4": "Essorage", "5": "Terminé"}, "running_states": [2, 3, 4]},
    "remaining_time": "2.11",
    "energy_cycle": {"prop": "2.12", "scale": 0.01},
    "power": {"prop": "2.1", "on": true},
    "auto_power_off": {"prop": "2.20", "keep_value": 0}
  },
  "dryer": {
    "remaining_time": "2.5",
    "power_w": "3.4"
  }
}
```

Clés disponibles : `status`, `fault`, `program`, `remaining_time` (min), `progress` (%), `power_w` (W), `energy_total` (kWh cumulés), `energy_cycle` (kWh du cycle), `water` (L), `temperature`, `spin_speed`, `drying_level`, `door`, `child_lock`, `power`, `auto_power_off`.
Options par clé : `scale`, `offset`, `map`, `running_states`, `invert` (porte / sécurité enfant), `on`/`off` (alimentation), `keep_value` (arrêt auto). Une clé à `null` supprime la valeur supposée. Une section peut aussi viser un appareil précis par son identifiant (`did`) au lieu de `washer` / `dryer`.

## Consommation

- `energy_total` ou `energy_cycle` mappé : capteur kWh en `total_increasing`, utilisable tel quel dans le tableau de bord Énergie (la remise à zéro à chaque cycle est gérée par HA).
- Seulement `power_w` : l'intégration calcule les kWh elle-même (capteur *Énergie (calculée)*).
- Rien de tout ça : l'appareil ne remonte pas sa consommation, il faudra une prise connectée.

## Maintien en éveil

Le commutateur **Maintenir éveillé** (activé par défaut) agit toutes les 60 s (réglable) :

- garde la session cloud et la connexion MQTT ouvertes ;
- si `power` est mappé : rallume l'appareil quand il s'est éteint ;
- si `auto_power_off` est mappé avec `keep_value` : remet l'arrêt automatique sur cette valeur.

Sans `power` / `auto_power_off` mappés, l'intégration n'écrit **jamais** rien sur l'appareil. Éteindre via le commutateur **Alimentation** met aussi en pause le maintien en éveil, sinon il rallumerait la machine.

À savoir : selon le firmware, le module Wi-Fi peut se couper complètement à l'extinction ; dans ce cas aucune commande cloud ne peut le réveiller, et seule la désactivation de l'arrêt automatique (si l'appareil l'expose) fonctionne. Le capteur **Joignable** indique si l'appareil répond.

## Dépannage

### `Error while executing request: Read timed out. (timeout=6)` dans le journal

C'est le bruit attendu quand la machine est **éteinte ou en sommeil profond** : le module Wi-Fi se coupe, le cloud Dreamehome répond mais l'appareil ne joint pas dans les 6 s impartis (l'appel est réessayé jusqu'à 2 fois, d'où plusieurs lignes). Tant que le capteur **Joignable** repasse à « Oui » quand tu allumes la machine — ou grâce au maintien en éveil — rien n'est cassé : les entités gardent leurs dernières valeurs entre-temps.

Si ces avertissements répétés polluent ton journal, réduis la verbosité de la couche réseau dans `configuration.yaml` :

```yaml
logger:
  logs:
    custom_components.dreame_laundry.cloud.protocol: debug
```

### L'appareil ne se réveille jamais

Vérifie que **Maintenir éveillé** est activé et que les propriétés `power` / `auto_power_off` sont mappées (sinon l'intégration n'écrit jamais sur l'appareil). Certains firmwares coupent totalement le Wi-Fi à l'extinction : dans ce cas seul `auto_power_off` peut aider, ou rallumer la machine manuellement avant de la commander.

## Entités

Capteurs : état, défaut, programme, temps restant, fin prévue, progression, puissance, énergie, eau, température, essorage, niveau de séchage, plus les `Propriété x.y` brutes.
Capteurs binaires : cycle en cours, joignable, porte, sécurité enfant.
Commutateurs : maintenir éveillé, alimentation. Boutons : scanner les propriétés, actualiser.

Le téléchargement des diagnostics (page de l'intégration) contient le mapping, les valeurs et les propriétés découvertes, identifiants masqués.

## Licence

MIT, voir [LICENSE](LICENSE). Le client cloud dans `cloud/` reste sous la licence MIT de Tasshack (`cloud/LICENSE.tasshack`).
