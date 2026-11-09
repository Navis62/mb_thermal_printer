---
paths:
  - "scripts/**"
  - "tests/test_scripts.py"
---

# Pipeline de données et d'images (`scripts/`)

Chaîne, menée par `scripts/update.sh` (lit `IMAGES_DIR` et `DATA_DIR` dans `settings.cfg`) :
`get_image_urls_from_scryfall.py` (données en masse `oracle-cards` → `DATA_DIR/creatures_image_urls.json`) →
`download_images_from_scryfall.py` (`IMAGES_DIR/<cmc>/<nom>.jpg`) → `convert_images.py`
(`IMAGES_DIR/<cmc>/converted_files/<nom>.bmp`) → nettoyage des JPG et des fichiers de `DATA_DIR`.
Ça tourne sous Linux, macOS, WSL ou Git Bash, et sur le Pi. C'est long et ça appelle Scryfall.

- **Scryfall** : un appel `GET /bulk-data/oracle-cards` puis le téléchargement du fichier ; les images viennent du
  CDN (`image_uris.normal`, 488x680), 12 fils, `Retry` sur 429/5xx. En-têtes `User-Agent` et `Accept` obligatoires.
  Avant d'ajouter un appel ou d'augmenter le parallélisme, relis `scryfall.com/docs/api`. Pas de scraping.
- **Filtre** (`is_valid_creature`) : face avant créature (`is_creature_front` : `Creature` dans la partie de
  `type_line` avant ` // `), hors jetons, emblèmes et art series, légale quelque part (pas les Un-cards), pas Arena
  seule, pas de préfixe `A-`. Les cartes à deux faces prennent l'image de la face avant. Le changer change le contenu
  de l'imprimante : seulement sur demande, avec le nombre de cartes concernées.
- **Dossiers de coût** : seuls les dossiers au nom en chiffres de `IMAGES_DIR` sont lus, convertis ou nettoyés
  (`cmc_dirs.py` côté Python, boucle `case` dans `update.sh`). `IMAGES_DIR` peut contenir autre chose (le dépôt et son
  `assets/`).
- **Rejouable et atomique** : chaque écriture passe par un fichier `.part` renommé à la fin, et les `.part` restants
  sont nettoyés au démarrage. Une carte dont le BMP existe n'est ni retéléchargée ni reconvertie. Garde ces deux
  propriétés.
- **Données générées** (dans `IMAGES_DIR` et `DATA_DIR`, hors du dépôt) : ne les supprime pas, ne les réécris pas
  pour un test. Pour essayer un script, travaille sur un petit échantillon dans un dossier temporaire (scratchpad).
- **Sortie attendue par le Pi** : `IMAGES_DIR/<cmc>/converted_files/*.bmp`, 1 bit, 384 px de large. Changer cette
  structure oblige à changer `momir_basic.py`, `/deploy-pi`, `.claude/rules/hardware.md` et le README.
- Noms de fichiers : `sanitise_name` retire `' " / \ : * ? < > |` et les points ou espaces finaux. Deux cartes au nom
  identique après nettoyage s'écrasent ; vérifie avant de changer la règle.
- `update.sh` : `set -e`, variables entre guillemets, réglages lus clé par clé (jamais `source settings.cfg`),
  `bash -n` avant de rendre. Les échecs de téléchargement n'empêchent pas la conversion mais donnent un code de
  sortie 1.
- Un script long affiche sa progression avec `Progress` (une ligne tous les 5 %) : c'est le seul signe de vie dans
  un journal ou en SSH.
- Les fonctions pures (filtre, URL d'image, noms, tramage) sont testées dans `tests/test_scripts.py` : un changement
  de règle s'accompagne de son test.
