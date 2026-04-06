import { ref } from 'vue'

import {
  deleteSavedHost as deleteSavedHostRequest,
  getSavedHosts as getSavedHostsRequest,
} from '../services/api.js'


function defaultDeps() {
  return {
    getSavedHostsApi: getSavedHostsRequest,
    deleteSavedHostApi: deleteSavedHostRequest,
  }
}


let savedHostsDeps = null


function resolveDeps() {
  return savedHostsDeps || defaultDeps()
}


export function setSavedHostsDependencies(overrides = {}) {
  savedHostsDeps = {
    ...defaultDeps(),
    ...overrides,
  }
}


export function resetSavedHostsDependencies() {
  savedHostsDeps = null
}


export function useSavedHosts() {
  const hosts = ref([])
  const scope = ref('mine')
  const loading = ref(false)
  const errorText = ref('')
  const deletingId = ref(null)

  async function loadHosts(nextScope = scope.value) {
    loading.value = true
    errorText.value = ''
    scope.value = nextScope
    try {
      const response = await resolveDeps().getSavedHostsApi(nextScope)
      hosts.value = response?.data?.hosts || []
      return hosts.value
    } catch (error) {
      errorText.value = error?.response?.data?.detail || error?.message || '读取已保存主机失败'
      throw error
    } finally {
      loading.value = false
    }
  }

  async function deleteHost(hostId) {
    deletingId.value = hostId
    errorText.value = ''
    try {
      await resolveDeps().deleteSavedHostApi(hostId)
      hosts.value = hosts.value.filter((item) => item.id !== hostId)
    } catch (error) {
      errorText.value = error?.response?.data?.detail || error?.message || '删除主机失败'
      throw error
    } finally {
      deletingId.value = null
    }
  }

  return {
    hosts,
    scope,
    loading,
    errorText,
    deletingId,
    loadHosts,
    deleteHost,
  }
}
