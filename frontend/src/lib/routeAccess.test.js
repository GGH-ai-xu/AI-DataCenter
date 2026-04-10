import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveRouteAccess } from './routeAccess.js'


test('anonymous users are redirected to login', () => {
  const result = resolveRouteAccess({
    path: '/',
    user: null,
    workspaceReady: false,
  })

  assert.deepEqual(result, { allow: false, redirectTo: '/login' })
})

test('password change required users are redirected to change password page', () => {
  const result = resolveRouteAccess({
    path: '/import',
    user: { id: 1, must_change_password: true },
    workspaceReady: false,
  })

  assert.deepEqual(result, { allow: false, redirectTo: '/change-password' })
})

test('authenticated users without imported workspace are redirected to import page', () => {
  const result = resolveRouteAccess({
    path: '/tasks',
    user: { id: 1, must_change_password: false },
    workspaceReady: false,
  })

  assert.deepEqual(result, { allow: false, redirectTo: '/import' })
})

test('ready users entering auth pages are redirected back to workspace', () => {
  const result = resolveRouteAccess({
    path: '/login',
    user: { id: 1, must_change_password: false },
    workspaceReady: true,
  })

  assert.deepEqual(result, { allow: false, redirectTo: '/' })
})

test('ready users can access console routes', () => {
  const result = resolveRouteAccess({
    path: '/monitor',
    user: { id: 1, must_change_password: false },
    workspaceReady: true,
  })

  assert.deepEqual(result, { allow: true, redirectTo: null })
})

test('ready users can access ai graph route', () => {
  const result = resolveRouteAccess({
    path: '/ai/graph',
    user: { id: 1, must_change_password: false },
    workspaceReady: true,
  })

  assert.deepEqual(result, { allow: true, redirectTo: null })
})
