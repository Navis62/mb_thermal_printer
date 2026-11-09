// Stop: if code changed during this turn, check every modified script before handing back.
//
//   checks-on-stop.mjs snapshot   # UserPromptSubmit: records the state of the modified files at the start of the turn
//   checks-on-stop.mjs            # Stop: runs the checks again only if that state changed since
//
// Work in progress by the user, already modified before the turn, therefore triggers nothing. Without a snapshot
// (hook added mid-session), it falls back to "a code file modified since the last commit".
// Checks: Python syntax (compile, never import: momir_basic.py needs RPi.GPIO), `bash -n` on shell scripts, ruff
// errors if ruff is installed, `tests/` (unittest) if that folder exists, and the guard-bash tests when a hook changed.
// A failure exits with code 2: Claude receives the end of the report and keeps going to fix it. `stop_hook_active`
// prevents a loop: on the second consecutive stop, the turn ends (the failure has already been reported once).
// The checks run in parallel, each under CHECK_TIMEOUT_MS, which stays below the Stop hook timeout in settings.json
// (180 s); a check that times out or cannot start counts as a failure.
import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const CODE = /\.(py|sh|mjs)$/;
const CHECK_TIMEOUT_MS = 150_000;

const data = JSON.parse(readFileSync(0, 'utf8') || '{}');
const root = resolve(process.env.CLAUDE_PROJECT_DIR || data.cwd || '.');
const session = String(data.session_id || 'no-session').replace(/[^\w-]/g, '_');
const state = join(tmpdir(), 'mb-thermal-printer-hooks', `${session}.txt`);

function changedCode() {
  const r = spawnSync('git', ['status', '--porcelain', '--untracked-files=all', '--', '*.py', '*.sh', '.claude/hooks', 'tests'], {
    cwd: root,
    encoding: 'utf8',
    timeout: 30_000,
  });
  return (r.stdout ?? '')
    .split('\n')
    .filter(Boolean)
    .map((line) => line.slice(3).split(' -> ').at(-1).replace(/^"|"$/g, ''))
    .filter((name) => CODE.test(name) && !name.startsWith('.venv/'));
}

function fingerprint() {
  const h = createHash('sha256');
  for (const name of changedCode().sort()) {
    const p = join(root, name);
    const st = existsSync(p) ? statSync(p) : null;
    h.update(`${p}|${st ? st.mtimeMs : 0}|${st ? st.size : -1}\n`);
  }
  return h.digest('hex');
}

function python() {
  for (const p of [join(root, '.venv', 'Scripts', 'python.exe'), join(root, '.venv', 'bin', 'python')]) {
    if (existsSync(p)) return p;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

// Resolves to null on success (or when `skipIf` says the tool is absent), or to a failure report (last 30 lines).
function run(label, cmd, args, skipIf) {
  return new Promise((done) => {
    const child = spawn(cmd, args, { cwd: root, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
    let out = '';
    child.stdout.on('data', (chunk) => (out += chunk));
    child.stderr.on('data', (chunk) => (out += chunk));
    const timer = setTimeout(() => {
      child.kill();
      done(`${label} did not finish within ${CHECK_TIMEOUT_MS / 1000} s; run it by hand.`);
    }, CHECK_TIMEOUT_MS);
    child.on('error', (err) => {
      clearTimeout(timer);
      done(`${label} could not start: ${err.message}`);
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code === 0 || (skipIf && skipIf.test(out))) return done(null);
      done(`${label} fails:\n${out.trim().split('\n').slice(-30).join('\n')}`);
    });
  });
}

try {
  if (process.argv[2] === 'snapshot') {
    mkdirSync(join(tmpdir(), 'mb-thermal-printer-hooks'), { recursive: true });
    writeFileSync(state, fingerprint(), 'utf8');
    process.exit(0);
  }
  if (data.stop_hook_active) process.exit(0);
  if (existsSync(state) ? readFileSync(state, 'utf8') === fingerprint() : changedCode().length === 0) process.exit(0);
} catch {
  process.exit(0);
}

const py = python();
const changed = changedCode();
const pyFiles = changed.filter((n) => n.endsWith('.py') && existsSync(join(root, n)));
const shFiles = changed.filter((n) => n.endsWith('.sh') && existsSync(join(root, n)));
const compile = 'import sys\nfor f in sys.argv[1:]:\n    compile(open(f, encoding="utf-8").read(), f, "exec")';

const checks = [];
if (pyFiles.length) {
  checks.push(run(`python syntax (${pyFiles.join(', ')})`, py, ['-c', compile, ...pyFiles]));
  checks.push(
    run('ruff (syntax, undefined names)', py, ['-m', 'ruff', 'check', '--quiet', '--no-cache', '--select', 'E9,F63,F7,F82', ...pyFiles], /No module named/i),
  );
}
for (const f of shFiles) checks.push(run(`bash -n ${f}`, 'bash', ['-n', f]));
if (existsSync(join(root, 'tests'))) checks.push(run('python -m unittest discover tests', py, ['-m', 'unittest', 'discover', '-s', 'tests']));
if (changed.some((n) => n.startsWith('.claude/hooks/'))) checks.push(run('node --test .claude/hooks/guard-bash.test.mjs', process.execPath, ['--test', '.claude/hooks/guard-bash.test.mjs']));

const failures = (await Promise.all(checks)).filter(Boolean);
if (failures.length) {
  process.stderr.write(`After your changes:\n\n${failures.join('\n\n')}\n`);
  process.exit(2);
}
