---
name: ship
description: "Livre le travail en cours de mb_thermal_printer : vérifications, commits petits et ordonnés, push vers origin (github.com/Navis62/mb_thermal_printer). Use only when the user runs /ship or explicitly asks to commit and push."
disable-model-invocation: true
argument-hint: "[--no-push]"
---

# ship

Un seul développeur. `/ship` vaut accord pour commiter et pousser **ce** travail, pas les suivants. Il ne déploie
rien sur le Pi : c'est `/deploy-pi`.

Branche : !`git branch --show-current`
État : !`git status --short`

## Étapes

1. **Vérifier** avec `/check`. Ne continue pas si une vérification échoue : rapporte l'échec.
2. **Relire** `git status` : ne commite jamais `.venv/`, `__pycache__/`, `settings.cfg`, `oracle-cards.jsonl.gz`,
   `creatures_image_urls.json`, des dossiers de coût (`0/` à `16/`, `converted_files/`), des `*.jpg` / `*.bmp` de
   cartes, un `.env`, une clé (`*.pem`, `*.key`), ni un réglage personnel (`.claude/settings.local.json`,
   `CLAUDE.local.md`). `.claude/` et `CLAUDE.md` ne sont pas suivis : ne les ajoute que si l'utilisateur le demande.
   Ajoute les fichiers un par un, pas `git add -A`.
3. **Commits** petits, un sujet chacun. Message **en anglais**, titre court à l'impératif qui dit ce qui change
   (« Wait for PRINT release before the next card »), puis, si le commit n'est pas trivial, un corps : pourquoi (le
   défaut ou le besoin), quoi, et la preuve (vérification faite, ce qui reste à essayer sur le Pi). Termine par la
   ligne d'attribution demandée par l'environnement.
4. **Push** : `git push -u origin <branche>`, sauf si `$ARGUMENTS` contient `--no-push`. Sur une autre branche que
   `main`, propose la fusion ou une PR sans la faire.
5. Rends compte : la liste des commits (`git log --oneline -5`) et le résultat du push.

## Garde-fous

Pas de `--force`, pas de `--no-verify`, pas de `--amend` d'un commit déjà poussé. Si le push est refusé (distant en
avance), rapporte-le et propose `git pull --rebase` sans le lancer.
