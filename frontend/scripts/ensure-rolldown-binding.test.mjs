import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildInstallFailureMessage,
  installBinding,
  resolveNpmInstallCommand,
} from './ensure-rolldown-binding.mjs'


test('buildInstallFailureMessage includes registry and npm output', () => {
  const message = buildInstallFailureMessage(
    '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
    {
      status: 1,
      signal: null,
      stdout: 'npm notice retrying request',
      stderr: 'npm ERR! ECONNRESET',
    },
    'https://registry.npmmirror.com',
  )

  assert.match(message, /failed to install @rolldown\/binding-win32-x64-msvc@1\.0\.0-rc\.11/)
  assert.match(message, /registry: https:\/\/registry\.npmmirror\.com/)
  assert.match(message, /exit status: 1/)
  assert.match(message, /stdout:\s+npm notice retrying request/)
  assert.match(message, /stderr:\s+npm ERR! ECONNRESET/)
})

test('installBinding forwards npm args and throws detailed error', () => {
  let received = null
  const installCommand = {
    filePath: 'E:\\Node.js\\node.exe',
    args: [
      'E:\\Node.js\\node_modules\\npm\\bin\\npm-cli.js',
      'install',
      '--no-save',
      '--package-lock=false',
      '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
    ],
  }
  const spawnSyncFn = (command, args, options) => {
    received = { command, args, options }
    return {
      status: 1,
      signal: null,
      stdout: 'npm notice retrying request',
      stderr: 'npm ERR! 404 Not Found',
    }
  }

  assert.throws(
    () => installBinding('@rolldown/binding-win32-x64-msvc@1.0.0-rc.11', spawnSyncFn, installCommand),
    /npm ERR! 404 Not Found/,
  )
  assert.equal(received.command, 'E:\\Node.js\\node.exe')
  assert.deepEqual(received.args, [
    'E:\\Node.js\\node_modules\\npm\\bin\\npm-cli.js',
    'install',
    '--no-save',
    '--package-lock=false',
    '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
  ])
  assert.equal(received.options.encoding, 'utf8')
  assert.equal(received.options.stdio, 'pipe')
})

test('resolveNpmInstallCommand prefers npm_execpath over npm.cmd lookup', () => {
  const command = resolveNpmInstallCommand(
    '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
    {
      processExecPath: 'E:\\Node.js\\node.exe',
      npmExecPath: 'E:\\Node.js\\node_modules\\npm\\bin\\npm-cli.js',
    },
  )

  assert.equal(command.filePath, 'E:\\Node.js\\node.exe')
  assert.deepEqual(command.args, [
    'E:\\Node.js\\node_modules\\npm\\bin\\npm-cli.js',
    'install',
    '--no-save',
    '--package-lock=false',
    '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
  ])
})

test('resolveNpmInstallCommand derives npm-cli.js from node.exe when npm_execpath is missing', () => {
  const command = resolveNpmInstallCommand(
    '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
    {
      platform: 'win32',
      processExecPath: 'E:\\Node.js\\node.exe',
      npmExecPath: '',
      existsSyncFn: (path) => path === 'E:\\Node.js\\node_modules\\npm\\bin\\npm-cli.js',
    },
  )

  assert.equal(command.filePath, 'E:\\Node.js\\node.exe')
  assert.deepEqual(command.args, [
    'E:\\Node.js\\node_modules\\npm\\bin\\npm-cli.js',
    'install',
    '--no-save',
    '--package-lock=false',
    '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
  ])
})

test('buildInstallFailureMessage includes spawn error details when process never started', () => {
  const message = buildInstallFailureMessage(
    '@rolldown/binding-win32-x64-msvc@1.0.0-rc.11',
    {
      status: null,
      signal: null,
      stdout: '',
      stderr: '',
      error: Object.assign(new Error('spawn npm.cmd ENOENT'), {
        code: 'ENOENT',
        syscall: 'spawn npm.cmd',
      }),
    },
    'https://registry.npmmirror.com',
  )

  assert.match(message, /exit status: unknown/)
  assert.match(message, /spawn error: spawn npm\.cmd ENOENT/)
  assert.match(message, /error code: ENOENT/)
  assert.match(message, /syscall: spawn npm\.cmd/)
})
