import test from 'node:test'
import assert from 'node:assert/strict'
import { createDomainRefreshCoordinator } from './domainRefresh.js'

test('deduplicates concurrent requests by key', async () => {
  let calls = 0
  const coordinator = createDomainRefreshCoordinator()
  const loader = async () => ({ calls: ++calls })
  const [first, second] = await Promise.all([
    coordinator.run('dashboard:governance', loader, { staleTime: 0 }),
    coordinator.run('dashboard:governance', loader, { staleTime: 0 }),
  ])

  assert.equal(calls, 1)
  assert.deepEqual(first, second)
})

test('reuses fresh cached data before stale time expires', async () => {
  let now = 1000
  let calls = 0
  const coordinator = createDomainRefreshCoordinator({ now: () => now })

  await coordinator.run(
    'monitor:system',
    async () => ({ calls: ++calls }),
    { staleTime: 5000 },
  )
  now = 2000

  const cached = await coordinator.run(
    'monitor:system',
    async () => ({ calls: ++calls }),
    { staleTime: 5000 },
  )

  assert.equal(calls, 1)
  assert.equal(cached.fromCache, true)
})

test('skips hidden refreshes unless forced', async () => {
  const coordinator = createDomainRefreshCoordinator({ isVisible: () => false })
  const skipped = await coordinator.run(
    'energy:overview',
    async () => ({ ok: true }),
    { staleTime: 0 },
  )

  assert.equal(skipped.skipped, 'hidden')

  const forced = await coordinator.run(
    'energy:overview',
    async () => ({ ok: true }),
    { force: true, staleTime: 0 },
  )

  assert.equal(forced.data.ok, true)
})
