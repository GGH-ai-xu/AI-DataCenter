import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app.js'
import { createDomainRefreshCoordinator } from '../lib/domainRefresh.js'

const coordinator = createDomainRefreshCoordinator()

function resolveKey(section, key) {
  const domainKey = typeof key === 'function' ? key() : key
  return {
    domainKey: domainKey ?? null,
    refreshKey: domainKey ? `${section}:${domainKey}` : section,
  }
}

function reportRefreshError(section, error) {
  console.error(`[useDomainRefresh] ${section} refresh failed`, error)
}

export function useDomainRefresh(options) {
  const store = useAppStore()
  const section = options.section
  const intervalMs = Number(options.intervalMs || 0)
  const staleTime = Number(options.staleTime || 0)
  const enabled = options.enabled || (() => true)
  let timer = null

  async function refresh(policy = {}) {
    if (!enabled()) {
      return null
    }

    const keyState = resolveKey(section, options.key)
    store.beginDomainRequest(section, keyState.domainKey)

    try {
      const result = await coordinator.run(
        keyState.refreshKey,
        options.loader,
        {
          force: policy.force === true,
          staleTime,
        },
      )

      if (result.data !== null && options.applyData) {
        options.applyData(result.data, result, keyState.domainKey)
      }

      store.completeDomainRequest(
        section,
        keyState.domainKey,
        result.data,
        result.lastUpdatedAt || 0,
      )
      return result
    } catch (error) {
      store.failDomainRequest(section, keyState.domainKey, error)
      throw error
    }
  }

  function refreshSilently(policy = {}) {
    return refresh(policy).catch((error) => {
      reportRefreshError(section, error)
      return null
    })
  }

  onMounted(() => {
    void refreshSilently()
    if (intervalMs > 0) {
      timer = setInterval(() => {
        void refreshSilently()
      }, intervalMs)
    }
  })

  onUnmounted(() => {
    if (timer) {
      clearInterval(timer)
    }
  })

  return { refresh }
}
