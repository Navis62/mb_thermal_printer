# mb_thermal_printer

Imprimante « Momir Basic » pour Magic: The Gathering : un Raspberry Pi (4 ou Zero 2 W), une imprimante thermique
QR204 (série), un écran OLED SSD1306 128x32 (I2C) et 3 boutons. On règle le coût converti de mana (0 à 16), on
appuie, une créature au hasard de ce coût s'imprime en monochrome. Projet perso, un seul développeur, développement
sous Windows, le programme final tourne sur le Pi. Fork de `oboyone/mb_thermal_printer` ; `origin` est
`github.com/Navis62/mb_thermal_printer`.
Le README décrit le montage, l'installation et les fichiers : @README.md

## Fichiers

- `momir_basic.py` : programme du Pi (boucle de scrutation, GPIO, OLED, impression). Démarré par systemd
  (`deploy/momir.service`), journal dans `journalctl -u momir`.
- `settings.cfg.example` → `settings.cfg` (non suivi) : `IMAGES_DIR`, `DATA_DIR`, options (`FONT_PATH`,
  `OLED_TIMEOUT`, `BUTTONS_ACTIVE_LOW`, `FEED_LINES`). Lu par `momir_basic.py` à l'import et par `scripts/update.sh`.
- `setup.sh` : première installation sur le Pi (apt, I2C/série, groupes, `.venv`, `settings.cfg`, service systemd).
- `scripts/update.sh` : chaîne complète, rejouable :
  1. `get_image_urls_from_scryfall.py` : données en masse Scryfall (`oracle-cards.jsonl.gz`) vers
     `creatures_image_urls.json`, dans `DATA_DIR` ;
  2. `download_images_from_scryfall.py` : JPG dans `IMAGES_DIR/<cmc>/` (12 fils, saute les cartes déjà converties) ;
  3. `convert_images.py` : BMP 1 bit de 384 px dans `IMAGES_DIR/<cmc>/converted_files/` (Pillow, Atkinson) ;
  4. supprime les JPG et les fichiers de `DATA_DIR`.
  `scripts/progress.py` : une ligne de progression tous les 5 %.
- `tests/` : `test_momir_basic.py` (matériel simulé par `sys.modules`), `test_scripts.py`.
- `assets/` : police, schéma de câblage, photos (originaux).

## Commandes

```bash
.venv/Scripts/python.exe -m unittest discover -s tests       # 43 tests, matériel simulé (Pillow + requests dans le .venv)
python -m py_compile momir_basic.py scripts/*.py tests/*.py   # syntaxe
bash -n scripts/update.sh && bash -n setup.sh                 # syntaxe des scripts shell
node --test .claude/hooks/*.test.mjs                          # tests du garde-fou
```

`momir_basic.py` importe `RPi.GPIO`, `escpos` et `luma` et lit `settings.cfg` à l'import : il **ne s'exécute pas
sous Windows** en vrai, seuls les tests (qui simulent tout) le chargent. L'essai réel se fait sur le Pi. Le pipeline
s'exécute ici, mais il est long et appelle Scryfall : seulement sur demande.

## Règles du dépôt

- Code, commentaires, noms, README et commits **en anglais** ; on échange avec l'utilisateur en français. Les
  messages de l'OLED sont en anglais et courts (128 px de large, vérifié par `test_messages_fit_the_oled`).
- Pas de chemin personnel en dur : tout passe par `settings.cfg`. `deploy/momir.service` suppose `/home/pi`,
  `setup.sh` l'adapte.
- Câblage et réglages matériels (broches BOARD 11/13/15, `/dev/serial0` à 9600 bauds, adresse I2C `0x3C`,
  largeur 384 px) : ne rien modifier sans le dire, on ne peut pas les tester ici. Voir `.claude/rules/hardware.md`.
- Données générées (`IMAGES_DIR/<cmc>/`, `converted_files/`, `oracle-cards.jsonl.gz`, `creatures_image_urls.json`) :
  hors du dépôt, jamais commitées, jamais supprimées sans demande (les régénérer prend des heures).
- `assets/` (police sous licence OFL, `wiring.jpg`, `photo-*.jpg`) et `LICENSE` sont des originaux : on ne les
  supprime ni ne les remplace.
- `settings.cfg` n'est pas suivi par git : un `git clean` l'effacerait.
- Pas de `pip install` hors `.venv`, de `ssh` / `rsync` vers le Pi ni de push sans demande : `/deploy-pi`, `/ship`.

## Où regarder

- Règles détaillées par zone : `.claude/rules/` (chargées selon les fichiers touchés).
- Agents : `mb-architect` (conception, lecture seule), `mb-hardware` (programme du Pi), `mb-pipeline` (données et
  images), `mb-tester`, `mb-reviewer` (relecture, lecture seule).
- Skills : `/check`, `/ship`, `/deploy-pi`, `/ub-mode`, `/tech-debt-audit`.
