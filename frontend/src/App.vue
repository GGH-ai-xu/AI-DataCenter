<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import GlobalToast from './components/GlobalToast.vue'
import {
  applyResolvedThemeToDocument,
  readStoredThemePreference,
  watchSystemTheme,
  writeStoredThemePreference,
} from './lib/themeMode.js'
import { setupInterceptor } from './services/api.js'
import { useAppStore } from './stores/app.js'
import { useAuthStore } from './stores/auth.js'


const router = useRouter()
const appStore = useAppStore()
const auth = useAuthStore()
const toastRef = ref(null)
let teardownSpotlight = null
let stopThemePreferenceWatch = null
let disposeSystemThemeWatch = null
let systemPrefersDark = true

function setupSpotlightTracking() {
  if (typeof window === 'undefined') return () => {}
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    return () => {}
  }

  const selector = [
    '.tech-card',
    '.btn-tech',
    '.workspace-tab',
    '.import-prep-tabs__item',
    '.app-primary-nav__item',
    '.app-mobile-nav__item',
    '.app-mobile-nav__action',
    '.overview-route',
    '.app-primary-sidebar__collapse-toggle',
    '.app-sidebar-brand-card__switch',
  ].join(', ')

  let previousTarget = null

  const clearTarget = (target) => {
    if (!target) return
    target.style.removeProperty('--spotlight-opacity')
  }

  const handlePointerMove = (event) => {
    if (!(event.target instanceof Element)) {
      clearTarget(previousTarget)
      previousTarget = null
      return
    }

    const target = event.target.closest(selector)
    if (!(target instanceof HTMLElement)) {
      clearTarget(previousTarget)
      previousTarget = null
      return
    }

    if (previousTarget && previousTarget !== target) {
      clearTarget(previousTarget)
    }

    const rect = target.getBoundingClientRect()
    target.style.setProperty('--spotlight-x', `${event.clientX - rect.left}px`)
    target.style.setProperty('--spotlight-y', `${event.clientY - rect.top}px`)
    target.style.setProperty('--spotlight-opacity', '1')
    previousTarget = target
  }

  const clearPrevious = () => {
    clearTarget(previousTarget)
    previousTarget = null
  }

  window.addEventListener('pointermove', handlePointerMove, { passive: true })
  window.addEventListener('blur', clearPrevious)
  document.addEventListener('pointerleave', clearPrevious)

  return () => {
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('blur', clearPrevious)
    document.removeEventListener('pointerleave', clearPrevious)
    clearPrevious()
  }
}

function syncTheme(systemDark = systemPrefersDark) {
  systemPrefersDark = Boolean(systemDark)
  appStore.syncResolvedTheme(systemPrefersDark)
  applyResolvedThemeToDocument(document.documentElement, appStore.resolvedTheme)
}

onMounted(() => {
  setupInterceptor({
    showToast: (message, type) => {
      toastRef.value?.show(message, type)
    },
    onUnauthorized: async () => {
      auth.forceLocalLogout()
      if (router.currentRoute.value.path !== '/login') {
        await router.replace('/login')
      }
    },
    onPasswordChangeRequired: async () => {
      if (router.currentRoute.value.path !== '/change-password') {
        await router.replace('/change-password')
      }
    },
  })

  const themeWatcher = watchSystemTheme(window, (matches) => {
    systemPrefersDark = matches
    if (appStore.themePreference === 'system') {
      syncTheme(systemPrefersDark)
    }
  })
  systemPrefersDark = themeWatcher.matches
  disposeSystemThemeWatch = themeWatcher.dispose
  appStore.hydrateThemePreference(
    readStoredThemePreference(window.localStorage),
    systemPrefersDark,
  )
  applyResolvedThemeToDocument(document.documentElement, appStore.resolvedTheme)
  stopThemePreferenceWatch = watch(
    () => appStore.themePreference,
    (preference) => {
      writeStoredThemePreference(window.localStorage, preference)
      syncTheme(systemPrefersDark)
    },
  )
  teardownSpotlight = setupSpotlightTracking()
})

onUnmounted(() => {
  stopThemePreferenceWatch?.()
  disposeSystemThemeWatch?.()
  teardownSpotlight?.()
})
</script>

<template>
  <router-view />
  <GlobalToast ref="toastRef" />
</template>
