---
name: check
description: "Vérification de mb_thermal_printer avant de considérer un travail fini ou de commiter : tests unittest, syntaxe Python et shell, tests du garde-fou si les hooks ont changé, cohérence du README et de settings.cfg.example. À utiliser après une modification de code, ou quand l'utilisateur demande « vérifie », « c'est bon ? »."
allowed-tools: Bash(.venv/Scripts/python.exe -m unittest *) Bash(python -m py_compile *) Bash(python -m unittest *) Bash(python -m ruff check *) Bash(bash -n *) Bash(node --test *) Bash(git status *) Bash(git diff *)
---

# check

Fichiers modifiés : !`git status --short`

1. `.venv/Scripts/python.exe -m unittest discover -s tests` (le `.venv` contient Pillow et requests ; le matériel
   du Pi est simulé). Rapporte le nombre exact de tests passés / échoués.
2. `python -m py_compile` sur chaque `.py` modifié (`momir_basic.py`, `scripts/*.py`, `tests/*.py`).
3. `bash -n` sur chaque `.sh` modifié (`scripts/update.sh`, `setup.sh`).
4. `python -m ruff check --select E9,F63,F7,F82 <fichiers>` si ruff est installé ; sinon dis-le et passe.
5. `node --test .claude/hooks/*.test.mjs` si `.claude/hooks/` a changé.
6. Si le diff touche `momir_basic.py`, `setup.sh` ou `deploy/` : liste ce qui **ne peut pas** être vérifié ici
   (boutons, OLED, impression, installation) et ce qu'il faudra essayer sur le Pi ; signale tout changement de
   broche, de baud, d'adresse I2C, de largeur d'image, de bornes du coût ou de texte de l'OLED.
7. Si le diff touche `scripts/` : le filtre des cartes, le parallélisme, les appels Scryfall ou la structure de sortie
   (`<cmc>/converted_files/*.bmp`) ont-ils changé ? Si oui, le README et `.claude/rules/pipeline.md` le disent-ils ?
8. Un réglage lu dans `settings.cfg` a-t-il son entrée commentée dans `settings.cfg.example` et dans le README ? Une
   dépendance nouvelle est-elle dans `requirements.txt` ?
9. `git status` : aucun fichier généré (`*.jpg` de cartes, `*.bmp`, `oracle-cards.jsonl.gz`,
   `creatures_image_urls.json`, dossiers de coût), `settings.cfg`, `.venv/` ou secret n'est prêt à être commité.
10. README : si le diff ajoute ou change un fichier, une étape ou une commande, vérifie qu'il le dit (« File
    reference », étapes d'installation).

Rends compte en quelques lignes : résultat exact de chaque étape (passés / échoués / sautés), et pour un échec la
cause probable avec `fichier:ligne`. Ne corrige rien sans le dire.
