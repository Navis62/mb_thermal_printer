---
paths:
  - "momir_basic.py"
  - "settings.cfg.example"
  - "setup.sh"
  - "deploy/**"
  - "tests/test_momir_basic.py"
---

# Programme du Pi (`momir_basic.py`) et son installation

- Il tourne sur un Raspberry Pi 4 ou Zero 2 W, démarré par systemd (`deploy/momir.service`, `Restart=on-failure`,
  abandon après 5 échecs en 5 min). Les erreurs vont dans le journal (`logging`). Une erreur d'impression ou de
  fichier est rattrapée dans `print_random_card` et affichée sur l'OLED (`MSG_NO_CARDS`, `MSG_ERROR`) : garde ce
  principe pour toute nouvelle opération qui touche le matériel.
- **Ne s'exécute pas sous Windows** (`RPi.GPIO`, `/dev/serial0`, I2C). Les tests remplacent les modules matériels
  dans `sys.modules` et simulent `settings.cfg` ; on vérifie par les tests, la compilation et la relecture. Ce qui
  touche vraiment le matériel s'essaie sur le Pi : dis-le.
- **Matériel, à ne pas modifier sans le dire** : numérotation `GPIO.BOARD`, boutons sur les broches 11 / 13 / 15,
  imprimante `Serial('/dev/serial0', 9600, 8N1)`, OLED `ssd1306` en I2C adresse `0x3C`, images de 384 px de large.
- Boutons : par défaut `PUD_DOWN`, appuyé = `GPIO.HIGH` (le bouton relie la broche au 3,3 V). Avec
  `BUTTONS_ACTIVE_LOW=true` : `PUD_UP`, appuyé = `GPIO.LOW`. Toute lecture passe par `_is_pressed`.
- OLED : l'écran fait 128x32 mais `ssd1306(serial)` est créé avec la taille par défaut (128x64) et le texte est
  dessiné à y=30. Point connu, à n'ajuster qu'après essai sur le montage.
- Coût converti : `CMC_MIN` / `CMC_MAX` (0 à 16). Messages OLED en anglais, courts (≤ ~123 px en police 16).
- Images : `IMAGES_DIR/<cmc>/converted_files/*.bmp` (`IMAGES_DIR` vient de `settings.cfg`). `list_cards` ne garde
  que les `.bmp` et met la liste en cache selon le `mtime` du dossier. Dossier vide ou absent : « No cards ».
- Impression : `_print_image` puis `FEED_LINES` lignes vides. Après une impression, on attend que le bouton soit
  relâché (un appui long ne doit pas imprimer deux cartes).
- Boucle : scrutation toutes les 50 ms (`POLL_INTERVAL`), anti-rebond de 200 ms ; ne la bloque pas plus longtemps
  que `display_message` (2 s). Mise en veille de l'OLED après `OLED_TIMEOUT` s ; l'appui qui réveille ne fait rien
  d'autre. `SIGTERM` devient `SystemExit` pour que `GPIO.cleanup()` passe.
- Police : `assets/FredokaOne-Regular.ttf` par défaut, `FONT_PATH` optionnel (repli sur la police embarquée).
- Une option de plus va dans `settings.cfg.example` et le README ; une dépendance de plus dans `requirements.txt`
  et, si apt la fournit, dans `setup.sh`.
- `setup.sh` et `momir.service` : `set -e`, variables entre guillemets, `bash -n` ; `setup.sh` ne se lance pas ici
  (sudo, apt, redémarrage).
