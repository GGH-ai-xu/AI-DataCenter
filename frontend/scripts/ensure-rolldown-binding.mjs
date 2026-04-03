import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(SCRIPT_DIR, '..');
const ROLLDOWN_PACKAGE_JSON = join(
  FRONTEND_ROOT,
  'node_modules',
  'rolldown',
  'package.json',
);
const NPM_COMMAND = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const DIRECT_BINDINGS = Object.freeze({
  'android:arm64': '@rolldown/binding-android-arm64',
  'darwin:arm64': '@rolldown/binding-darwin-arm64',
  'darwin:x64': '@rolldown/binding-darwin-x64',
  'freebsd:x64': '@rolldown/binding-freebsd-x64',
  'linux:arm': '@rolldown/binding-linux-arm-gnueabihf',
  'linux:ppc64': '@rolldown/binding-linux-ppc64-gnu',
  'linux:s390x': '@rolldown/binding-linux-s390x-gnu',
  'win32:arm64': '@rolldown/binding-win32-arm64-msvc',
  'win32:x64': '@rolldown/binding-win32-x64-msvc',
});
const LINUX_LIBC_BINDINGS = Object.freeze({
  'arm64:gnu': '@rolldown/binding-linux-arm64-gnu',
  'arm64:musl': '@rolldown/binding-linux-arm64-musl',
  'x64:gnu': '@rolldown/binding-linux-x64-gnu',
  'x64:musl': '@rolldown/binding-linux-x64-musl',
});

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function detectLinuxLibc() {
  const report = process.report?.getReport?.().header ?? {};
  return report.glibcVersionRuntime ? 'gnu' : 'musl';
}

function resolveBindingName() {
  const key = `${process.platform}:${process.arch}`;
  if (DIRECT_BINDINGS[key]) {
    return DIRECT_BINDINGS[key];
  }
  if (process.platform !== 'linux') {
    return null;
  }
  const libcKey = `${process.arch}:${detectLinuxLibc()}`;
  return LINUX_LIBC_BINDINGS[libcKey] ?? null;
}

function getRolldownVersion() {
  if (!existsSync(ROLLDOWN_PACKAGE_JSON)) {
    throw new Error(
      'rolldown is not installed. Run `npm install` or `npm ci` before starting Vite.',
    );
  }
  const packageJson = readJson(ROLLDOWN_PACKAGE_JSON);
  return packageJson.version;
}

function bindingDirectory(packageName) {
  const [scope, name] = packageName.split('/');
  return join(FRONTEND_ROOT, 'node_modules', scope, name);
}

function hasBindingBinary(packageName) {
  const dir = bindingDirectory(packageName);
  if (!existsSync(join(dir, 'package.json'))) {
    return false;
  }
  return readdirSync(dir).some((entry) => entry.endsWith('.node'));
}

function installBinding(packageSpecifier) {
  const args = ['install', '--no-save', '--package-lock=false', packageSpecifier];
  const result = spawnSync(NPM_COMMAND, args, {
    cwd: FRONTEND_ROOT,
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    throw new Error(`failed to install ${packageSpecifier}`);
  }
}

function main() {
  const bindingName = resolveBindingName();
  if (!bindingName) {
    console.warn(
      `[ensure-rolldown-binding] no mapping for ${process.platform}:${process.arch}; skipping binding preflight.`,
    );
    return;
  }

  if (hasBindingBinary(bindingName)) {
    return;
  }

  const packageSpecifier = `${bindingName}@${getRolldownVersion()}`;
  console.warn(
    `[ensure-rolldown-binding] missing native binding ${bindingName}; installing ${packageSpecifier}.`,
  );
  installBinding(packageSpecifier);

  if (!hasBindingBinary(bindingName)) {
    throw new Error(`installed ${packageSpecifier}, but the native binary is still missing`);
  }
}

main();
