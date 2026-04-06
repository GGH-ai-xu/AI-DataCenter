import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'

import { useAppStore } from './app.js'
import {
  resetAuthStoreDependencies,
  setAuthStoreDependencies,
  useAuthStore,
} from './auth.js'


function resetStores() {
  setActivePinia(createPinia())
}


test.afterEach(() => {
  resetAuthStoreDependencies()
})

test('hydrate restores session token and current user', async () => {
  resetStores()
  setAuthStoreDependencies({
    readSessionToken: () => 'persisted-token',
    meApi: async () => ({
      data: {
        user: {
          id: 7,
          username: 'alice',
          role: 'member',
          must_change_password: false,
        },
      },
    }),
  })

  const store = useAuthStore()
  await store.hydrate()

  assert.equal(store.token, 'persisted-token')
  assert.equal(store.currentUser.username, 'alice')
  assert.equal(store.isAuthenticated, true)
  assert.equal(store.ready, true)
})

test('login persists token and exposes mustChangePassword state', async () => {
  resetStores()
  let writtenToken = ''
  setAuthStoreDependencies({
    writeSessionToken: (value) => {
      writtenToken = value
    },
    loginApi: async () => ({
      data: {
        token: 'new-token',
        user: {
          id: 1,
          username: 'admin',
          role: 'admin',
          must_change_password: true,
        },
      },
    }),
  })

  const store = useAuthStore()
  await store.login({
    username: 'admin',
    password: 'TempPassw0rd!',
  })

  assert.equal(writtenToken, 'new-token')
  assert.equal(store.token, 'new-token')
  assert.equal(store.mustChangePassword, true)
})

test('changePassword clears mustChangePassword flag in store', async () => {
  resetStores()
  setAuthStoreDependencies({
    changePasswordApi: async () => ({ data: { success: true } }),
  })

  const store = useAuthStore()
  store.currentUser = {
    id: 1,
    username: 'admin',
    role: 'admin',
    must_change_password: true,
  }

  await store.changePassword({
    currentPassword: 'TempPassw0rd!',
    newPassword: 'NewPassw0rd!',
  })

  assert.equal(store.mustChangePassword, false)
})

test('changePassword sends snake_case payload to backend api', async () => {
  resetStores()
  let receivedPayload = null
  setAuthStoreDependencies({
    changePasswordApi: async (payload) => {
      receivedPayload = payload
      return { data: { success: true } }
    },
  })

  const store = useAuthStore()
  store.currentUser = {
    id: 1,
    username: 'admin',
    role: 'admin',
    must_change_password: true,
  }

  await store.changePassword({
    currentPassword: 'TempPassw0rd!',
    newPassword: 'NewPassw0rd!',
  })

  assert.deepEqual(receivedPayload, {
    current_password: 'TempPassw0rd!',
    new_password: 'NewPassw0rd!',
  })
})

test('forceLocalLogout clears auth state and imported workspace state', () => {
  resetStores()
  let cleared = false
  setAuthStoreDependencies({
    clearSessionToken: () => {
      cleared = true
    },
  })

  const auth = useAuthStore()
  const app = useAppStore()
  auth.token = 'persisted-token'
  auth.currentUser = {
    id: 3,
    username: 'alice',
    role: 'member',
    must_change_password: false,
  }
  app.setImportContext({ valid: true, imported_gpu_indexes: [0] })

  auth.forceLocalLogout()

  assert.equal(cleared, true)
  assert.equal(auth.token, '')
  assert.equal(auth.currentUser, null)
  assert.equal(app.workspaceReady, false)
  assert.equal(app.importContext, null)
})
