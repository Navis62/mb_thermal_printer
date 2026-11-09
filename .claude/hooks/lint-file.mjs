// PostToolUse (Edit, Write): syntax check of the Python / shell file that was just modified.
//   .py  -> python -m py_compile, then ruff (only real errors: syntax, undefined names) if ruff is installed
//   .sh  -> bash -n
// Errors: exit code 2, the report (stderr) is shown to Claude, which fixes it right away.
// momir_basic.py needs RPi.GPIO and cannot run on Windows: it is compiled, never imported or executed.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, join, relative, resolve } from 'node:path';

const data = JSON.parse(readFileSync(0, 'utf8') || '{}');
const root = resolve(process.env.CLAUDE_PROJECT_DIR || data.cwd || '.');
const file = data.tool_input?.file_path ?? '';
// On Windows, a file on another drive gives an absolute "relative" path (C:\...), hence the isAbsolute check.
const relNative = relative(root, resolve(file));
const rel = relNative.replaceAll('\\', '/');

const inRepo = rel && !isAbsolute(relNative) && !rel.startsWith('..') && !/^(\.venv|\.git|__pycache__)\//.test(rel);
if (!inRepo || !existsSync(file)) process.exit(0);

function python() {
  for (const p of [join(root, '.venv', 'Scripts', 'python.exe'), join(root, '.venv', 'bin', 'python')]) {
    if (existsSync(p)) return p;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function run(cmd, args) {
  return spawnSync(cmd, args, { cwd: root, encoding: 'utf8', timeout: 25_000 });
}

const problems = [];
if (rel.endsWith('.py')) {
  const py = python();
  // Plain compile() in memory: no __pycache__ file left behind, nothing imported.
  const c = spawnSync(py, ['-c', 'import sys; compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec")', rel], {
    cwd: root,
    encoding: 'utf8',
    timeout: 25_000,
  });
  if (!c.error && c.status !== 0) problems.push(`syntax error:\n${(c.stderr || c.stdout).trim()}`);
  else if (!c.error) {
    const r = run(py, ['-m', 'ruff', 'check', '--quiet', '--select', 'E9,F63,F7,F82', '--no-cache', rel]);
    const missing = /No module named/i.test(r.stderr ?? '');
    if (!r.error && !missing && r.status !== 0) problems.push(`ruff:\n${[r.stdout, r.stderr].join('').trim()}`);
  }
} else if (rel.endsWith('.sh')) {
  const r = run('bash', ['-n', rel]);
  if (!r.error && r.status !== 0) problems.push(`bash -n:\n${(r.stderr || r.stdout).trim()}`);
}

if (problems.length) {
  process.stderr.write(`Problems in ${rel}:\n${problems.join('\n')}\n`);
  process.exit(2);
}
