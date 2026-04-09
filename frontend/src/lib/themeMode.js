export const THEME_PREFERENCES = Object.freeze(['system', 'dark', 'light'])
export const DEFAULT_THEME_PREFERENCE = 'system'
export const THEME_STORAGE_KEY = 'ai-datacenter-theme-preference'

export function normalizeThemePreference(value) {
  return THEME_PREFERENCES.includes(value) ? value : DEFAULT_THEME_PREFERENCE
}

export function resolveThemeFromPreference(preference, systemPrefersDark) {
  const normalized = normalizeThemePreference(preference)
  if (normalized === 'dark') return 'dark'
  if (normalized === 'light') return 'light'
  return systemPrefersDark ? 'dark' : 'light'
}

export function applyResolvedThemeToDocument(root, resolvedTheme) {
  root.dataset.theme = resolvedTheme
  root.style.setProperty('color-scheme', resolvedTheme)
}

export function readStoredThemePreference(storage) {
  return normalizeThemePreference(storage?.getItem(THEME_STORAGE_KEY))
}

export function writeStoredThemePreference(storage, preference) {
  const normalized = normalizeThemePreference(preference)
  storage?.setItem(THEME_STORAGE_KEY, normalized)
  return normalized
}

export function watchSystemTheme(windowObject, onChange) {
  const query = windowObject.matchMedia('(prefers-color-scheme: dark)')
  const handleChange = (event) => {
    onChange(Boolean(event.matches))
  }

  query.addEventListener('change', handleChange)

  return {
    matches: Boolean(query.matches),
    dispose() {
      query.removeEventListener('change', handleChange)
    },
  }
}

export function readThemeVar(name, root = document.documentElement) {
  return getComputedStyle(root).getPropertyValue(name).trim()
}
