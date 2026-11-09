// Tests for guard-bash.mjs: node --test .claude/hooks/*.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { blocked } from './guard-bash.mjs';

const BLOCKED = [
  'git push --force origin main',
  'git push -f',
  'git push origin +main',
  'git commit --no-verify -m x',
  'git reset --hard',
  'git -C . reset --hard',
  'git clean -fd',
  'git checkout .',
  'git checkout HEAD -- momir_basic.py',
  'git checkout -f main',
  'git switch -f main',
  'git restore momir_basic.py',
  'git restore --worktree --staged .',
  'git stash drop',
  'rm FredokaOne-Regular.ttf',
  'Remove-Item wiring.jpg',
  'rm creatures_image_urls.json',
  'rm -rf 7',
  'rm -rf 12/',
  'rm -rf ./5',
  'rm 3/*.jpg',
  'find . -name "*.bmp" -exec rm {} +',
  'Remove-Item -Recurse -Force .\\16',
  'crontab -r',
  'ssh pi@raspberrypi.local "sudo rm -rf /home/navis/Desktop/momir"',
  'ssh pi@raspberrypi.local sudo reboot',
  'echo ok && git reset --hard',
  'bash -c "git reset --hard"',
  'rm assets/photo-inside.jpg',
  'rm -rf assets',
  'git rm LICENSE',
  'rm -rf ~/momir_images',
  'rm -rf /home/pi/Desktop/momir/7/converted_files',
  'rm ~/momir_data/oracle-cards.jsonl.gz',
  'find ~/momir_images -name "*.bmp" -delete',
  'ssh pi@raspberrypi.local sudo systemctl disable momir',
  'rsync -av --delete images/ pi@raspberrypi.local:/home/pi/momir_images/',
];

const ALLOWED = [
  'git push origin feat/x',
  'git push -u origin feat/x',
  'git status',
  'git checkout -b feature',
  'git switch main',
  'git restore --staged momir_basic.py',
  'git stash pop',
  'git commit -m "x" -m "notes about rm and the 7 folder"',
  'git commit -m "explain why git reset --hard is blocked"',
  'git clean -n\necho -f',
  'rm -rf __pycache__',
  'rm .venv/Lib/site-packages/x.pyc',
  'ls 7/',
  'crontab -l',
  'scp momir_basic.py pi@raspberrypi.local:/home/navis/',
  'python -m py_compile momir_basic.py',
  'bash -n scripts/update.sh',
  'rm -rf scripts/__pycache__ tests/__pycache__',
  'find . -name "*.pyc" -delete',
  'rsync -av --progress images/ pi@raspberrypi.local:/home/pi/momir_images/',
  'ssh pi@raspberrypi.local systemctl status momir',
  '.venv/Scripts/python.exe -m unittest discover -s tests',
];

test('blocks destructive commands', () => {
  for (const command of BLOCKED) assert.ok(blocked(command), `should block: ${command}`);
});

test('lets harmless commands through', () => {
  for (const command of ALLOWED) assert.equal(blocked(command), null, `should allow: ${command}`);
});
