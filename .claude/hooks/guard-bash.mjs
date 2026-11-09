// PreToolUse (Bash, PowerShell): blocks commands that would destroy work, git history or the generated data.
// Exit code 2 = command refused; the reason (stderr) is sent back to Claude. Plain Node, no dependency.
//
// The command is split into simple commands (lines, `;`, `|`, `&`, `&&`, `||`) after joining continuation lines
// (`\` in sh, backtick in PowerShell), and each rule is tested on one simple command at a time, so a flag on a
// later line is never attached to an earlier command. A rule is a list of patterns that must all match.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// `git` in command position (start of the simple command, or right after `(`, `$(`, `{`, a quote or a backtick, as in
// `bash -c "git ..."`), so that a commit message quoting a git command is not mistaken for it. Then git's global
// options (`-C dir`, `-c key=value`, `--no-pager`...) and the given subcommand.
const git = (sub) =>
  String.raw`(?:^|[("'\`{]|\$\()\s*(?:sudo\s+)?git(?:\.exe)?(?:\s+(?:-[Cc]\s+\S+|--[\w-]+(?:=\S+)?))*\s+(?:${sub})\b`;
// A delete command in command position (start of the simple command, or after sudo, xargs, -exec, git), or `find -delete`.
const DELETE = String.raw`(?:(?:^\s*(?:sudo\s+|xargs(?:\s+-\S+)*\s+|git\s+)?|-exec\s+)(?:rm|del|rmdir|Remove-Item|ri|erase|rd|unlink|rimraf)\b|\bfind\b.*\s-delete\b)`;

export const RULES = [
  [[git('push'), String.raw`(--force\b|--force-with-lease\b|\s-\w*f\b|\s\+\S)`], 'force push is forbidden: it rewrites remote history'],
  [[git(String.raw`[\w-]+`), String.raw`\s--no-verify\b`],'--no-verify is forbidden: fix the cause instead of skipping the checks'],
  [[git('reset'), String.raw`\s--(hard|merge)\b`], 'git reset --hard is forbidden: uncommitted work would be lost'],
  [[git('clean'), String.raw`(\s-\w*f|\s--force\b)`], 'git clean -f is forbidden: it would delete untracked files (.claude/, CLAUDE.md, settings.cfg are untracked)'],
  [[git('checkout'), String.raw`\s--(\s|$)`], 'git checkout -- <path> is forbidden: it would discard uncommitted changes'],
  [[git('checkout'), String.raw`\s(\.|:/)(\s|$)`], 'git checkout . is forbidden: it would discard all uncommitted changes'],
  [[git('checkout|switch'), String.raw`\s(-\w*f\b|--force\b|--discard-changes\b)`], 'git checkout/switch -f is forbidden: it would discard uncommitted changes'],
  // `git restore --staged` alone only unstages; any other restore overwrites the working tree.
  [[git('restore'), String.raw`^(?!.*\s(--staged|-S)\b)`], 'git restore is forbidden: it would discard uncommitted changes'],
  [[git('restore'), String.raw`\s(--worktree|-W)\b`], 'git restore --worktree is forbidden: it would discard uncommitted changes'],
  [[git('stash'), String.raw`\s(drop|clear)\b`], 'git stash drop/clear is forbidden: stashed work would be lost'],
  // Originals that nothing can regenerate: assets/ (font, wiring diagram, photos) and the license.
  [[DELETE, String.raw`(FredokaOne|wiring\.jpg|photo-\w+\.jpg|\bassets\b|\bLICENSE\b)`], 'deleting assets/ (font, wiring diagram, photos) or LICENSE is forbidden: these are originals'],
  // Generated data: rebuilding it takes hours of Scryfall downloads and conversion.
  [[DELETE, String.raw`(creatures_image_urls\.json|oracle-cards|AtomicCards\.json|converted_files|momir_images|momir_data|\.(jpg|bmp|pbm)\b|\b(1[0-6]|[0-9])(?:[/\\"']|\s*$))`],
    'deleting generated card data (images, converted_files, Scryfall files, cmc folders) is refused: regenerating it takes hours'],
  // Some Pis may still start the program from crontab: emptying it would remove every job.
  [[String.raw`\bcrontab\s+(?:-\w+\s+)*-r\b`], 'crontab -r is forbidden: it would remove every scheduled job on the Pi'],
  [[String.raw`\b(ssh|scp|rsync)\b`, String.raw`\b(rm\s+-\w*r\w*|mkfs|dd\s+if=|shutdown|reboot|poweroff|systemctl\s+(?:disable|mask))\b`], 'destructive command sent to the Pi is refused: run it yourself if it is really needed'],
  [[String.raw`\brsync\b`, String.raw`\s--delete`], 'rsync --delete is refused: it would remove the cards on the Pi that are missing locally'],
];

export function simpleCommands(command) {
  return command
    .replace(/[\\`]\r?\n/g, ' ')
    .split(/\r?\n|&&|\|\||[;|&]/)
    .filter((part) => part.trim());
}

export function blocked(command) {
  for (const part of simpleCommands(command)) {
    for (const [patterns, reason] of RULES) {
      if (patterns.every((p) => new RegExp(p, 'i').test(part))) return reason;
    }
  }
  return null;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const data = JSON.parse(readFileSync(0, 'utf8') || '{}');
  const reason = blocked(data.tool_input?.command ?? '');
  if (reason) {
    process.stderr.write(`Blocked by .claude/hooks/guard-bash.mjs: ${reason}. Ask the user whether it is really needed.\n`);
    process.exit(2);
  }
}
