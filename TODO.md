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
- [x] **B5** 🟠 `momir_basic.py` : le bouton PRINT n'a pas de détection de front, un appui prolongé réimprime une carte.
- [x] **B6** 🟠 `momir_basic.py` : messages d'erreur OLED tronqués / illisibles (`str(e)[:20]`), « Already at max! » probablement rogné. Utiliser des messages courts prédéfinis.
- [x] **B7** 🟠 `momir_basic.py` : pas de handler `SIGTERM`, `GPIO.cleanup()` non exécuté à l'arrêt par `kill` / systemd ; traceback sur `Ctrl+C`.
- [x] **B8** 🟢 `scripts/download_images_from_scryfall.py` : fichiers temporaires `tmpXXXX` orphelins si le script est tué (ajouter un suffixe `.part` et les nettoyer).
- [x] **B9** 🟢 `scripts/download_images_from_scryfall.py` : code retour toujours 0 malgré des échecs, pas de retry / backoff sur 429/5xx.
- [x] **B10** 🟢 `scripts/get_image_urls_from_scryfall.py` : `scryfallOracleId` non protégé (`KeyError` = plantage complet).
- [x] **B11** 🟢 `scripts/get_image_urls_from_scryfall.py` : les cartes Alchemy digitales (sans préfixe `A-`) ne sont pas filtrées.

## ✨ Améliorations

### Pipeline de données
- [x] **A1** 🟠 Remplacer MTGJSON par le bulk `oracle-cards` de Scryfall (supprime un téléchargement et ~25 appels API par lot).
- [x] **A2** 🟠 Télécharger l'image `normal` (488 px) au lieu de `large` (suffisant pour 384 px d'impression).
- [x] **A3** 🟢 Sauter le téléchargement si le JPG existe déjà (conversion précédemment interrompue).
- [x] **A4** 🟢 Écriture atomique + `encoding='utf-8'` pour `creatures_image_urls.json`.
- [x] **A5** 🟢 Remplacer ImageMagick par Pillow (une dépendance en moins, dithering Floyd-Steinberg contrôlable).
- [ ] **A6** 🟢 Élaguer les BMP des cartes qui ne sont plus dans la liste.

### Programme principal
- [ ] **A7** 🟠 Boutons GPIO par interruptions (`add_event_detect` + `bouncetime`) au lieu du polling.
- [x] **A8** 🟢 Mettre en cache la liste des fichiers par CMC (éviter `os.listdir` à chaque impression).
- [ ] **A9** 🟢 Détection papier / imprimante (`paper_status()`, si le RX est câblé) affichée sur l'OLED.
- [x] **A10** 🟢 Mise en veille de l'OLED après inactivité (burn-in).
- [x] **A11** 🟠 Remplacer le cron `@reboot` par un service systemd (`Restart=on-failure`, logs journald).
- [ ] **A12** 🟢 Module de config partagé lu par les scripts Python, pour supprimer le parsing `grep` de `scripts/update.sh`.
- [x] **A13** 🟢 `FONT_PATH` relatif au dépôt par défaut.

### Packaging et tests
- [x] **A14** 🟠 Ajouter un `requirements.txt`.
- [x] **A15** 🟢 Tests unitaires : `tests/test_scripts.py` (scripts) et `tests/test_momir_basic.py` (matériel simulé) — 33 tests.

## 🧹 Nettoyages

- [x] **N1** 🟠 Supprimer `scripts/convert_images_to_monochrome.sh` (code mort, chemin codé en dur, non appelé par `scripts/update.sh`) et le retirer du tableau du README.
- [x] **N2** 🟠 Ajouter un `.gitattributes` (`* text=auto`, `*.sh text eol=lf`) et normaliser les fins de ligne (`momir_basic.py` et `scripts/get_image_urls_from_scryfall.py` sont en CRLF dans le dépôt).
- [x] **N3** 🟢 `scripts/update.sh` : numérotation des étapes incohérente (`[1/4]`…`[4/4]` puis `[5/5]`) et en-tête à mettre à jour.
- [x] **N4** 🟢 README : `---` en double (lignes 9-11).
- [x] **N5** 🟢 README : URL de clone (`mb_thermal_printer`) ≠ nom du dossier local.
- [x] **N6** 🟢 README : documenter l'activation I²C / port série matériel (`raspi-config`) et PEP 668 (venv ou `--break-system-packages`).
- [x] **N7** 🟢 README : mentionner l'étape 5 de `scripts/update.sh` (suppression des JPG et JSON temporaires).
- [x] **N8** 🟢 `.gitignore` : ajouter `__pycache__/`, `.venv/`, `tmp*`.
- [x] **N9** 🟢 Harmoniser `print` / `logging` entre les scripts, renommer les variables `_printer` / `_serial` / `_display` de `init_hardware`.

---

## ✅ Fait

- [x] 2026-10-06 — Analyse du projet et rédaction de cette liste.
- [x] 2026-10-06 — `momir_basic.py` : A8 (liste des BMP en cache, rafraîchie quand le dossier change, donc pas de redémarrage après `update.sh` ; ignore aussi les `*.bmp.part`), A10 (OLED éteint après `OLED_TIMEOUT` s, 300 par défaut, 0 = jamais ; un bouton le rallume sans autre action), A13 (`FONT_PATH` optionnel, repli sur la police fournie si absent — évite un plantage avec un ancien `settings.cfg`), N9 (variables de `init_hardware` renommées ; `print` conservé dans les scripts CLI, `logging` dans le service). A15 : `tests/test_momir_basic.py`, 33 tests au total.
- ⏸ Écartés pour l'instant, à décider : A6 (suppression de BMP, destructif), A7 (interruptions GPIO : comportement à valider sur de vrais boutons), A9 (détection papier : dépend du câblage RX), A12 (parsing de `settings.cfg` dans `update.sh`, fonctionne et testé).
- [x] 2026-10-06 — A1, A4, B11 : `scripts/get_image_urls_from_scryfall.py` utilise désormais le bulk Scryfall `oracle-cards` (JSON Lines gzip, 25 Mo, ~3 s) au lieu de MTGJSON + ~250 appels API. Filtre : créatures, hors jetons/emblèmes, légales dans au moins un format, hors cartes Arena-only (Alchemy). Résultat réel : 17 946 créatures, double-faces incluses, 0 collision de nom. `ijson`, `curl` et `gunzip` ne sont plus requis ; `update.sh` passe à 4 étapes ; écriture atomique des fichiers. Testé contre Scryfall (extraction + téléchargement/conversion de 5 vraies cartes).
- [x] 2026-10-06 — A11 : `deploy/momir.service` (systemd, `Restart=on-failure`, logs journald) à la place du cron ; README mis à jour. Non testé sur un Pi (écrit sans systemd ici). A15 (partiel) : `tests/test_scripts.py`, 18 tests.
- [x] 2026-10-06 — A5 : nouveau `scripts/convert_images.py` (Pillow, parallèle, écriture atomique via `.part`, code retour 1 en cas d'échec) ; ImageMagick n'est plus requis, `update.sh` et README mis à jour. Testé avec de vrais JPG (BMP 1 bit de 384×535, rendu vérifié visuellement, JPG corrompu, BMP existant, `.part` périmé) ; non comparé à ImageMagick, absent de cette machine.
- [x] 2026-10-06 — `scripts/download_images_from_scryfall.py` : B8 (fichiers `.part` nettoyés au démarrage), B9 (retry/backoff 429/5xx, code retour 1 en cas d'échec ; `update.sh` convertit quand même les images reçues puis termine en erreur), A3 (JPG déjà téléchargés non retéléchargés). A2 : image `normal` (488 px) au lieu de `large`. A14 : `requirements.txt`. Testé avec un serveur HTTP local (succès, 404, JPG existant, BMP existant, `.part` périmé).
- [x] 2026-10-06 — `momir_basic.py` : B5 (attente du relâchement du bouton PRINT après impression), B6 (messages OLED courts et mesurés avec la vraie police : `Max reached`, `Min reached`, `No cards`, `Print error` ; l'erreur détaillée reste dans les logs), B7 (SIGTERM converti en sortie normale, `Ctrl+C` sans traceback, `GPIO.cleanup()` garanti). Testé avec des faux modules matériel ; pas encore testé sur le Pi.
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
