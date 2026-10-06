# Suivi du projet

Dernière mise à jour : 2026-10-06

Légende : `[ ]` à faire · `[x]` fait · priorité 🔴 haute / 🟠 moyenne / 🟢 basse.
Les identifiants (B = bug, A = amélioration, N = nettoyage) servent à référencer les commits.

---

## 🐞 Bugs

- [x] **B1** 🔴 `scripts/get_image_urls_from_scryfall.py` : `ijson.items(f, 'data')` charge tout `AtomicCards.json` en RAM (OOM probable sur Pi Zero 2 W). Utiliser `ijson.kvitems(f, 'data')`.
- [x] **B2** 🔴 `scripts/get_image_urls_from_scryfall.py` : les cartes double-face (transform, MDFC) n'ont pas d'`image_uris` racine et sont ignorées. Repli sur `card_faces[0]["image_uris"]`.
- [x] **B3** 🔴 `scripts/get_image_urls_from_scryfall.py` : en-têtes `User-Agent` / `Accept` manquants (exigés par Scryfall), pas de gestion du 429 ni de retry, lot en échec affiché comme « done ».
- [x] **B4** 🟠 `scripts/update.sh` : `~` non expansé dans `IMAGES_DIR` / `DATA_DIR` (le parsing `grep` ne gère pas non plus les guillemets ni les commentaires en fin de ligne).
- [ ] **B5** 🟠 `momir_basic.py` : le bouton PRINT n'a pas de détection de front, un appui prolongé réimprime une carte.
- [ ] **B6** 🟠 `momir_basic.py` : messages d'erreur OLED tronqués / illisibles (`str(e)[:20]`), « Already at max! » probablement rogné. Utiliser des messages courts prédéfinis.
- [ ] **B7** 🟠 `momir_basic.py` : pas de handler `SIGTERM`, `GPIO.cleanup()` non exécuté à l'arrêt par `kill` / systemd ; traceback sur `Ctrl+C`.
- [ ] **B8** 🟢 `scripts/download_images_from_scryfall.py` : fichiers temporaires `tmpXXXX` orphelins si le script est tué (ajouter un suffixe `.part` et les nettoyer).
- [ ] **B9** 🟢 `scripts/download_images_from_scryfall.py` : code retour toujours 0 malgré des échecs, pas de retry / backoff sur 429/5xx.
- [x] **B10** 🟢 `scripts/get_image_urls_from_scryfall.py` : `scryfallOracleId` non protégé (`KeyError` = plantage complet).
- [ ] **B11** 🟢 `scripts/get_image_urls_from_scryfall.py` : les cartes Alchemy digitales (sans préfixe `A-`) ne sont pas filtrées.

## ✨ Améliorations

### Pipeline de données
- [ ] **A1** 🟠 Remplacer MTGJSON par le bulk `oracle-cards` de Scryfall (supprime un téléchargement et ~25 appels API par lot).
- [ ] **A2** 🟠 Télécharger l'image `normal` (488 px) au lieu de `large` (suffisant pour 384 px d'impression).
- [ ] **A3** 🟢 Sauter le téléchargement si le JPG existe déjà (conversion précédemment interrompue).
- [ ] **A4** 🟢 Écriture atomique + `encoding='utf-8'` pour `creatures_image_urls.json`.
- [ ] **A5** 🟢 Remplacer ImageMagick par Pillow (une dépendance en moins, dithering Floyd-Steinberg contrôlable).
- [ ] **A6** 🟢 Élaguer les BMP des cartes qui ne sont plus dans la liste.

### Programme principal
- [ ] **A7** 🟠 Boutons GPIO par interruptions (`add_event_detect` + `bouncetime`) au lieu du polling.
- [ ] **A8** 🟢 Mettre en cache la liste des fichiers par CMC (éviter `os.listdir` à chaque impression).
- [ ] **A9** 🟢 Détection papier / imprimante (`paper_status()`, si le RX est câblé) affichée sur l'OLED.
- [ ] **A10** 🟢 Mise en veille de l'OLED après inactivité (burn-in).
- [ ] **A11** 🟠 Remplacer le cron `@reboot` par un service systemd (`Restart=on-failure`, logs journald).
- [ ] **A12** 🟢 Module de config partagé lu par les scripts Python, pour supprimer le parsing `grep` de `scripts/update.sh`.
- [ ] **A13** 🟢 `FONT_PATH` relatif au dépôt par défaut.

### Packaging et tests
- [ ] **A14** 🟠 Ajouter un `requirements.txt`.
- [ ] **A15** 🟢 Tests unitaires : `is_valid_creature`, `sanitise_name`, sélection d'image (`momir_basic` testable avec des mocks).

## 🧹 Nettoyages

- [x] **N1** 🟠 Supprimer `scripts/convert_images_to_monochrome.sh` (code mort, chemin codé en dur, non appelé par `scripts/update.sh`) et le retirer du tableau du README.
- [x] **N2** 🟠 Ajouter un `.gitattributes` (`* text=auto`, `*.sh text eol=lf`) et normaliser les fins de ligne (`momir_basic.py` et `scripts/get_image_urls_from_scryfall.py` sont en CRLF dans le dépôt).
- [x] **N3** 🟢 `scripts/update.sh` : numérotation des étapes incohérente (`[1/4]`…`[4/4]` puis `[5/5]`) et en-tête à mettre à jour.
- [x] **N4** 🟢 README : `---` en double (lignes 9-11).
- [x] **N5** 🟢 README : URL de clone (`mb_thermal_printer`) ≠ nom du dossier local.
- [x] **N6** 🟢 README : documenter l'activation I²C / port série matériel (`raspi-config`) et PEP 668 (venv ou `--break-system-packages`).
- [x] **N7** 🟢 README : mentionner l'étape 5 de `scripts/update.sh` (suppression des JPG et JSON temporaires).
- [x] **N8** 🟢 `.gitignore` : ajouter `__pycache__/`, `.venv/`, `tmp*`.
- [ ] **N9** 🟢 Harmoniser `print` / `logging` entre les scripts, renommer les variables `_printer` / `_serial` / `_display` de `init_hardware`.

---

## ✅ Fait

- [x] 2026-10-06 — Analyse du projet et rédaction de cette liste.
- [x] 2026-10-06 — B4 : `scripts/update.sh` expanse `~` comme `momir_basic.py` (testé avec CRLF, espaces et `~`). N2 : `.gitattributes` + renormalisation (`momir_basic.py` passe en LF). N3 : étapes numérotées `/5`, en-tête complété. N1 : `convert_images_to_monochrome.sh` supprimé. N4, N6, N7 : README (doublon `---`, I²C/série/PEP 668, étape 5 de `update.sh`). N8 : `.gitignore` (`__pycache__/`, `*.pyc`, `.venv/`) ; le motif `tmp*` n'a pas été ajouté, les temporaires étant écrits dans `IMAGES_DIR`, hors dépôt (voir B8).
- [x] 2026-10-06 — Dépôt GitHub : nouveau dépôt privé `arthur-lagenebre/momir_thermal_printer` (origin), ancien dépôt `Navis62/mb_thermal_printer` conservé comme remote `upstream` ; URL de clone et chemins `/home/pi/...` du README et de `settings.cfg.example` renommés en `momir_thermal_printer` (N5).
- [x] 2026-10-06 — Corrections B1, B2, B3, B10 dans `scripts/get_image_urls_from_scryfall.py` : lecture en streaming (`kvitems`, seul l'oracle ID est gardé), repli sur `card_faces[0]` pour les cartes double-face, en-têtes Scryfall + retry/backoff 429/5xx (timeout 30 s, lots en échec signalés), `scryfallOracleId` protégé. Testé avec un faux `AtomicCards.json` et une API simulée ; nécessite `ijson>=3`.
- [x] 2026-10-06 — Tri des fichiers : `scripts/` (update.sh, scripts Python, conversion) et `assets/` (police, schéma de câblage) ; `momir_basic.py` reste à la racine ; chemins mis à jour dans `update.sh`, `settings.cfg.example` et le README.
- [x] Avant l'analyse (historique git) — Cleanup `scripts/update.sh` : suppression des JPG, `AtomicCards.json` et `creatures_image_urls.json` (PR #2).
- [x] Avant l'analyse (historique git) — `momir_basic.py` : logging, `GPIO.cleanup()`, init matérielle dans une fonction, erreurs sur l'OLED (PR #3).

---

## Ordre recommandé

1. B1, B2, B3 : les bloquants (mémoire, cartes manquantes, API).
2. B4, N2 : chemins `~` et fins de ligne.
3. N1, N3 à N7 : nettoyage du code mort et du README.
4. B5, A11, A14 : confort d'utilisation sur le Pi.
