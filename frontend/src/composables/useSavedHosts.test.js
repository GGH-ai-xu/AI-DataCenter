import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resetSavedHostsDependencies,
  setSavedHostsDependencies,
  useSavedHosts,
} from './useSavedHosts.js'


test.afterEach(() => {
  resetSavedHostsDependencies()
})

test('loadHosts hydrates saved host list for selected scope', async () => {
  setSavedHostsDependencies({
    getSavedHostsApi: async (scope) => ({
      data: {
        hosts: [
          { id: 1, label: '训练机 A', owner_username: scope === 'all' ? 'alice' : undefined },
        ],
      },
    }),
  })

  const savedHosts = useSavedHosts()
  await savedHosts.loadHosts('all')

  assert.equal(savedHosts.scope.value, 'all')
  assert.equal(savedHosts.hosts.value.length, 1)
  assert.equal(savedHosts.hosts.value[0].label, '训练机 A')
})

test('deleteHost removes item from current saved host list', async () => {
  setSavedHostsDependencies({
    deleteSavedHostApi: async () => ({ data: { success: true } }),
  })

  const savedHosts = useSavedHosts()
  savedHosts.hosts.value = [
    { id: 1, label: '训练机 A' },
    { id: 2, label: '训练机 B' },
  ]

  await savedHosts.deleteHost(1)

  assert.deepEqual(savedHosts.hosts.value.map((item) => item.id), [2])
})
