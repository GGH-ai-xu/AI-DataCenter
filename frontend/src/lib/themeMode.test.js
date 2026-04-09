import test from 'node:test'
import assert from 'node:assert/strict'

import {
  THEME_PREFERENCES,
  DEFAULT_THEME_PREFERENCE,
  normalizeThemePreference,
  resolveThemeFromPreference,
  applyResolvedThemeToDocument,
  watchSystemTheme,
} from './themeMode.js'

test('normalizeThemePreference falls back to system for invalid values', () => {
  assert.equal(DEFAULT_THEME_PREFERENCE, 'system')
  assert.equal(normalizeThemePreference('dark'), 'dark')
  assert.equal(normalizeThemePreference('light'), 'light')
  assert.equal(normalizeThemePreference('system'), 'system')
  assert.equal(normalizeThemePreference('unexpected'), 'system')
  assert.deepEqual(THEME_PREFERENCES, ['system', 'dark', 'light'])
})

test('resolveThemeFromPreference respects explicit overrides before system state', () => {
  assert.equal(resolveThemeFromPreference('dark', false), 'dark')
  assert.equal(resolveThemeFromPreference('light', true), 'light')
  assert.equal(resolveThemeFromPreference('system', true), 'dark')
  assert.equal(resolveThemeFromPreference('system', false), 'light')
})

test('applyResolvedThemeToDocument updates dataset theme and color scheme', () => {
  const root = {
    dataset: {},
    style: {
      applied: {},
      setProperty(name, value) {
        this.applied[name] = value
      },
    },
  }

  applyResolvedThemeToDocument(root, 'light')
  assert.equal(root.dataset.theme, 'light')
  assert.equal(root.style.applied['color-scheme'], 'light')
})

test('watchSystemTheme returns a dispose function that unregisters the listener', () => {
  let removed = false
  const query = {
    matches: true,
    addEventListener(_name, handler) {
      this.handler = handler
    },
    removeEventListener(_name, handler) {
      removed = this.handler === handler
    },
  }

  const watcher = watchSystemTheme({ matchMedia: () => query }, () => {})
  watcher.dispose()

  assert.equal(removed, true)
})
