import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  changePassword,
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
} from '../services/api.js'
import {
  clearSessionToken,
  readSessionToken,
  writeSessionToken,
} from '../lib/authSession.js'
import { useAppStore } from './app.js'


function defaultDeps() {
  return {
    loginApi: loginRequest,
    meApi: getCurrentUser,
    logoutApi: logoutRequest,
    changePasswordApi: changePassword,
    readSessionToken,
    writeSessionToken,
    clearSessionToken,
  }
}


let authStoreDeps = null


function resolveDeps() {
  return authStoreDeps || defaultDeps()
}


function clearWorkspaceState() {
  useAppStore().resetRuntimeState()
}


function normalizeChangePasswordPayload(payload = {}) {
  return {
    current_password: payload.currentPassword || '',
    new_password: payload.newPassword || '',
  }
}


export function setAuthStoreDependencies(overrides = {}) {
  authStoreDeps = {
    ...defaultDeps(),
    ...overrides,
  }
}


export function resetAuthStoreDependencies() {
  authStoreDeps = null
}


export const useAuthStore = defineStore('auth', () => {
  const token = ref('')
  const currentUser = ref(null)
  const ready = ref(false)
  const busy = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value && currentUser.value))
  const mustChangePassword = computed(() => Boolean(currentUser.value?.must_change_password))

  function applySession(nextToken, user) {
    token.value = String(nextToken || '').trim()
    currentUser.value = user || null
  }

  function clearLocalState() {
    const deps = resolveDeps()
    deps.clearSessionToken()
    applySession('', null)
    ready.value = true
    clearWorkspaceState()
  }

  async function hydrate() {
    const deps = resolveDeps()
    const storedToken = deps.readSessionToken()
    if (!storedToken) {
      clearLocalState()
      return null
    }

    busy.value = true
    token.value = storedToken
    try {
      const response = await deps.meApi()
      currentUser.value = response?.data?.user || null
      ready.value = true
      return currentUser.value
    } catch (error) {
      clearLocalState()
      if (error?.response?.status !== 401) {
        throw error
      }
      return null
    } finally {
      busy.value = false
    }
  }

  async function login(payload) {
    const deps = resolveDeps()
    busy.value = true
    try {
      const response = await deps.loginApi(payload)
      const nextToken = response?.data?.token || ''
      const user = response?.data?.user || null
      deps.writeSessionToken(nextToken)
      clearWorkspaceState()
      applySession(nextToken, user)
      ready.value = true
      return user
    } finally {
      busy.value = false
    }
  }

  async function logout() {
    const deps = resolveDeps()
    busy.value = true
    try {
      await deps.logoutApi()
    } finally {
      clearLocalState()
      busy.value = false
    }
  }

  async function changePassword(payload) {
    const deps = resolveDeps()
    busy.value = true
    try {
      await deps.changePasswordApi(normalizeChangePasswordPayload(payload))
      if (currentUser.value) {
        currentUser.value = {
          ...currentUser.value,
          must_change_password: false,
        }
      }
      clearWorkspaceState()
      return currentUser.value
    } finally {
      busy.value = false
    }
  }

  function forceLocalLogout() {
    clearLocalState()
  }

  return {
    token,
    currentUser,
    ready,
    busy,
    isAuthenticated,
    mustChangePassword,
    hydrate,
    login,
    logout,
    changePassword,
    forceLocalLogout,
  }
})
