import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve, win32 as win32Path } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(SCRIPT_DIR, '..');
const ROLLDOWN_PACKAGE_JSON = join(
  FRONTEND_ROOT,
  'node_modules',
  'rolldown',
  'package.json',
);
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
const NPM_REGISTRY = process.env.npm_config_registry || '';
const NPM_INSTALL_BASE_ARGS = Object.freeze([
  'install',
  '--no-save',
  '--package-lock=false',
]);

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

function buildInstallArgs(packageSpecifier) {
  return [...NPM_INSTALL_BASE_ARGS, packageSpecifier];
}

function npmCommandForPlatform(platform) {
  return platform === 'win32' ? 'npm.cmd' : 'npm';
}

function resolveBundledWindowsNpmCli(processExecPath, existsSyncFn) {
  const bundledCliPath = win32Path.join(
    win32Path.dirname(processExecPath),
    'node_modules',
    'npm',
    'bin',
    'npm-cli.js',
  );
  return existsSyncFn(bundledCliPath) ? bundledCliPath : null;
}

export function resolveNpmInstallCommand(packageSpecifier, options = {}) {
  const platform = options.platform ?? process.platform;
  const processExecPath = options.processExecPath ?? process.execPath;
  const npmExecPath = options.npmExecPath ?? process.env.npm_execpath;
  const existsSyncFn = options.existsSyncFn ?? existsSync;
  const installArgs = buildInstallArgs(packageSpecifier);

  if (npmExecPath) {
    return { filePath: processExecPath, args: [npmExecPath, ...installArgs] };
  }
  if (platform !== 'win32') {
    return { filePath: npmCommandForPlatform(platform), args: installArgs };
  }
  const bundledNpmCliPath = resolveBundledWindowsNpmCli(processExecPath, existsSyncFn);
  if (bundledNpmCliPath) {
    return { filePath: processExecPath, args: [bundledNpmCliPath, ...installArgs] };
  }
  throw new Error(
    `failed to resolve npm CLI for Windows install (process.execPath=${processExecPath})`,
  );
}

export function buildInstallFailureMessage(packageSpecifier, result, registry = NPM_REGISTRY) {
  const lines = [`failed to install ${packageSpecifier}`];
  if (registry) {
    lines.push(`registry: ${registry}`);
  }
  lines.push(`exit status: ${result.status ?? 'unknown'}`);
  if (result.signal) {
    lines.push(`signal: ${result.signal}`);
  }
  if (result.error) {
    lines.push(`spawn error: ${result.error.message}`);
    if (result.error.code) {
      lines.push(`error code: ${result.error.code}`);
    }
    if (result.error.syscall) {
      lines.push(`syscall: ${result.error.syscall}`);
    }
    if (result.error.path) {
      lines.push(`path: ${result.error.path}`);
    }
    if (result.error.spawnargs?.length) {
      lines.push(`spawn args: ${result.error.spawnargs.join(' ')}`);
    }
  }
  const stdout = String(result.stdout ?? '').trim();
  const stderr = String(result.stderr ?? '').trim();
  if (stdout) {
    lines.push(`stdout:\n${stdout}`);
  }
  if (stderr) {
    lines.push(`stderr:\n${stderr}`);
  }
  return lines.join('\n');
}

export function installBinding(
  packageSpecifier,
  spawnSyncFn = spawnSync,
  installCommand = resolveNpmInstallCommand(packageSpecifier),
) {
  const result = spawnSyncFn(installCommand.filePath, installCommand.args, {
    cwd: FRONTEND_ROOT,
    encoding: 'utf8',
    stdio: 'pipe',
  });
  if (result.error || result.status !== 0) {
    throw new Error(buildInstallFailureMessage(packageSpecifier, result));
  }
}

export function main() {
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

const isDirectRun = process.argv[1]
  && resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isDirectRun) {
  main();
}
