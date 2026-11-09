---
name: deploy-pi
description: "Prépare le déploiement de mb_thermal_printer sur le Raspberry Pi : vérifie le code, contrôle les images converties, et donne les commandes (git pull ou setup.sh, rsync des images, systemctl) à lancer soi-même. Use only when the user runs /deploy-pi or explicitly asks to deploy to the Pi."
disable-model-invocation: true
argument-hint: "[program|images|all]"
allowed-tools: Bash(.venv/Scripts/python.exe -m unittest *) Bash(python -m py_compile *) Bash(git status *) Bash(git diff *) Bash(git log *)
---

# deploy-pi

Le Pi est un appareil réel, hors de ce dépôt. Cette skill **prépare et vérifie** ; elle ne se connecte pas au Pi
(`ssh`, `scp`, `rsync` demandent l'accord de l'utilisateur à chaque fois) et n'éteint ni ne redémarre rien.

Cible : `$ARGUMENTS` (`program`, `images` ou `all`, par défaut `program`).
État : !`git status --short`

## Étapes

1. **Vérifier** : `/check`. Ne prépare rien si une vérification échoue.
2. **Demander ce qui manque** : nom d'hôte ou IP du Pi, utilisateur SSH, dossier du dépôt sur le Pi, valeur de
   `IMAGES_DIR` dans le `settings.cfg` du Pi. Ne les devine pas (`setup.sh` propose `~/momir_images`, l'exemple
   `/home/pi/Desktop/momir`).
3. **Programme** (`program` ou `all`) : le Pi est un clone git du dépôt. Le code doit être poussé (`/ship`) avant ;
   sinon dis-le. Commandes à donner :
   - première installation : `git clone https://github.com/Navis62/mb_thermal_printer.git`, puis `./setup.sh` en
     utilisateur normal (pas `sudo`), puis redémarrage ;
   - mise à jour : `cd <dépôt> && git pull --ff-only`, et `.venv/bin/pip install -r requirements.txt` si
     `requirements.txt` a changé (vérifie avec `git diff` depuis le dernier déploiement si l'utilisateur le connaît),
     puis `sudo systemctl restart momir`. Si `deploy/momir.service` a changé : relancer `./setup.sh -y`.
   Signale tout nouveau réglage à ajouter au `settings.cfg` du Pi (comparer avec `settings.cfg.example`).
4. **Images** (`images` ou `all`) : sur la machine de conversion, le Pi attend
   `IMAGES_DIR/<cmc>/converted_files/*.bmp` **tel quel** : on n'aplatit rien, on ne renomme rien. Compte les `.bmp`
   par coût (0 à 16) et signale un dossier vide ou absent (le bouton d'impression affichera « No cards ») et tout
   `.part` ou `.jpg` restant (conversion interrompue : relancer `scripts/update.sh`). Commande :
   `rsync -av --progress <IMAGES_DIR local>/ <user>@<pi>:<IMAGES_DIR du Pi>/`. Pas de `--delete` sans demande. Le
   programme relit un dossier quand il change : pas besoin de redémarrer.
5. **Essai sur le Pi** (à faire par l'utilisateur) : `systemctl status momir`, `journalctl -u momir -f` ; vérifier
   le coût sur l'OLED, un +/- aux deux bornes (0 et 16), une impression, un appui long sur Imprimer (une seule
   carte). Si le compteur monte tout seul : `BUTTONS_ACTIVE_LOW=true` dans `settings.cfg`.
6. Si une ancienne ligne `@reboot` de crontab lance encore le programme, conseille de la retirer avec `crontab -e`
   (jamais `crontab -r`).

Rends compte : ce qui est prêt, ce qui manque, les commandes, une par bloc. Rien n'est envoyé.
