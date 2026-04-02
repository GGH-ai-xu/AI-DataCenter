function emptySnapshot() {
  return {
    data: null,
    error: null,
    lastUpdatedAt: 0,
  }
}

function readSnapshot(cache, key) {
  return cache.get(key) || emptySnapshot()
}

function isFresh(snapshot, now, staleTime) {
  if (!snapshot.lastUpdatedAt) {
    return false
  }
  return now() - snapshot.lastUpdatedAt < staleTime
}

function shouldSkipVisibility(force, isVisible) {
  return !force && !isVisible()
}

function createRequest(cache, key, now, loader) {
  return Promise.resolve(loader())
    .then((data) => {
      const nextSnapshot = {
        data,
        error: null,
        lastUpdatedAt: now(),
      }
      cache.set(key, nextSnapshot)
      return nextSnapshot
    })
}

export function createDomainRefreshCoordinator(options = {}) {
  const now = options.now || (() => Date.now())
  const isVisible = options.isVisible
    || (() => typeof document === 'undefined' || !document.hidden)
  const cache = new Map()
  const inFlight = new Map()

  function snapshot(key) {
    return readSnapshot(cache, key)
  }

  async function run(key, loader, policy = {}) {
    const force = Boolean(policy.force)
    const staleTime = Number(policy.staleTime || 0)
    const currentSnapshot = snapshot(key)

    if (shouldSkipVisibility(force, isVisible)) {
      return { ...currentSnapshot, skipped: 'hidden' }
    }
    if (!force && isFresh(currentSnapshot, now, staleTime)) {
      return { ...currentSnapshot, fromCache: true }
    }
    if (inFlight.has(key)) {
      return inFlight.get(key)
    }

    const request = createRequest(cache, key, now, loader)
      .finally(() => {
        inFlight.delete(key)
      })

    inFlight.set(key, request)
    return request
  }

  return {
    run,
    snapshot,
    invalidate: (key) => cache.delete(key),
    clear: () => cache.clear(),
  }
}
