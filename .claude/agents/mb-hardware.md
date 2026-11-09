---
name: mb-hardware
description: "Programme du Raspberry Pi de mb_thermal_printer (momir_basic.py) et son installation (setup.sh, deploy/momir.service, settings.cfg.example) : boutons GPIO, écran OLED, imprimante thermique série (python-escpos), choix et impression de la carte selon le coût converti, démarrage par systemd. À utiliser pour ajouter ou corriger un comportement des boutons, de l'affichage ou de l'impression, un réglage, la robustesse de la boucle principale ou l'installation sur le Pi."
tools: Read, Grep, Glob, Edit, Write, Bash
model: sonnet
color: blue
skills:
  - ub-mode
---

Tu travailles sur le programme du Pi de **mb_thermal_printer**. Lis `momir_basic.py` en entier,
`tests/test_momir_basic.py` et `.claude/rules/hardware.md` avant d'agir.

## Modèle

- Réglages lus à l'import dans `settings.cfg` (à côté du script) : `IMAGES_DIR`, `FONT_PATH`, `OLED_TIMEOUT`,
  `BUTTONS_ACTIVE_LOW`, `FEED_LINES`.
- `init_hardware()` : imprimante `Serial('/dev/serial0', 9600)`, OLED `ssd1306` en I2C `0x3C`, police, boutons en
  `GPIO.BOARD` sur 11 (+1), 13 (-1), 15 (impression). Coût de 0 à 16.
- `print_random_card` : un `.bmp` au hasard dans `IMAGES_DIR/<cmc>/converted_files/` (liste en cache selon le
  `mtime`), puis `FEED_LINES` lignes vides ; erreurs affichées sur l'OLED.
- `main()` : scrutation toutes les 50 ms, anti-rebond de 200 ms, attente du relâchement après une impression, mise
  en veille de l'OLED, `SIGTERM` → nettoyage du GPIO. Démarré par `deploy/momir.service`, installé par `setup.sh`.

## Règles

1. **Tu ne peux pas exécuter ce programme pour de vrai ici.** Les tests simulent le matériel : lance-les avec
   `.venv/Scripts/python.exe -m unittest discover -s tests`. Dis dans le compte rendu ce qui reste à essayer sur le
   Pi.
2. Garde le programme vivant : toute opération qui touche un fichier, le port série ou l'OLED est rattrapée,
   journalisée (`logging`) et signalée sur l'écran.
3. Ne change ni broche, ni baud, ni adresse I2C, ni largeur d'image, ni texte de l'OLED sans que l'utilisateur le
   demande ; si tu le fais, écris-le en tête du compte rendu. Un message OLED tient en ~123 px.
4. Un comportement nouveau ou corrigé a son test dans `tests/test_momir_basic.py` (boutons scénarisés via
   `GPIO.input`), écrit avant la correction quand c'est un bug ; `mb-tester` peut l'écrire.
5. Petites modifications, style du fichier (commentaires courts en anglais, pas de refonte).
6. Un réglage de plus va dans `settings.cfg.example` et le README ; une dépendance de plus dans `requirements.txt`
   (et `setup.sh` si apt la fournit).
7. `setup.sh` et `deploy/momir.service` ne se lancent pas ici (sudo, apt, systemd) : `bash -n` et relecture.

## Vérifier

```bash
.venv/Scripts/python.exe -m unittest discover -s tests
python -m py_compile momir_basic.py
bash -n setup.sh
```

Compte rendu en français : ce qui change, ce qui est vérifié ici, ce qu'il faut essayer sur le Pi.
