import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'

import { createImportWorkspaceController } from './createImportWorkspaceController.js'


function createSavedHostsStub(hosts = []) {
  return {
    hosts: ref(hosts),
    scope: ref('mine'),
    loading: ref(false),
    errorText: ref(''),
    deletingId: ref(null),
    loadHosts: async () => hosts,
    deleteHost: async () => ({ data: { success: true } }),
  }
}

function createStoreStub() {
  return {
    importContext: null,
    workspaceReady: false,
    setImportContext(value) {
      this.importContext = value
    },
    setWorkspaceReady(value) {
      this.workspaceReady = Boolean(value)
    },
  }
}

function createRouterStub() {
  return {
    replaced: [],
    async replace(path) {
      this.replaced.push(path)
    },
  }
}

test('saved host scan keeps binding and advances to hardware', async () => {
  const scanPayloads = []
  const controller = createImportWorkspaceController({
    router: createRouterStub(),
    store: createStoreStub(),
    auth: { currentUser: { role: 'admin' } },
    savedHosts: createSavedHostsStub([
      {
        id: 1,
        label: 'ssh',
        provider_type: 'ssh_linux',
        host: '10.151.225.108',
        port: 22,
        username: 'dell',
        auth_type: 'password',
        credential_status: 'ok',
      },
    ]),
    api: {
      getImportContext: async () => ({ data: { imported_gpu_indexes: [] } }),
      scanImportContext: async (payload) => {
        scanPayloads.push(payload)
        return {
          data: {
            success: true,
            message: '扫描成功',
            provider: {
              provider_type: 'ssh_linux',
              label: 'ssh',
              host: '10.151.225.108',
              port: 22,
              username: 'dell',
              auth_type: 'password',
            },
            gpus: [{ index: 0 }, { index: 2 }],
          },
        }
      },
      commitImportContext: async () => {
        throw new Error('not used in this test')
      },
    },
  })

  await controller.handleSavedHostScan(1)

  assert.deepEqual(scanPayloads, [{ saved_host_id: 1 }])
  assert.equal(controller.selectedSavedHostId.value, 1)
  assert.equal(controller.activeStage.value, 'hardware')
  assert.deepEqual(controller.selectedGpuIndexes.value, [0, 2])
  assert.equal(controller.savedHostSummary.value.target, 'dell@10.151.225.108:22')
})

test('saved host import continues to commit saved_host_id only', async () => {
  const commitPayloads = []
  const router = createRouterStub()
  const store = createStoreStub()
  const controller = createImportWorkspaceController({
    router,
    store,
    auth: { currentUser: { role: 'admin' } },
    savedHosts: createSavedHostsStub([
      {
        id: 1,
        label: 'ssh',
        provider_type: 'ssh_linux',
        host: '10.151.225.108',
        port: 22,
        username: 'dell',
        auth_type: 'password',
        credential_status: 'ok',
      },
    ]),
    api: {
      getImportContext: async () => ({ data: { imported_gpu_indexes: [] } }),
      scanImportContext: async () => ({
        data: {
          success: true,
          message: '扫描成功',
          provider: {
            provider_type: 'ssh_linux',
            label: 'ssh',
            host: '10.151.225.108',
            port: 22,
            username: 'dell',
            auth_type: 'password',
          },
          gpus: [{ index: 0 }, { index: 1 }],
        },
      }),
      commitImportContext: async (payload) => {
        commitPayloads.push(payload)
        return {
          data: {
            import_context: {
              valid: true,
              imported_gpu_indexes: payload.gpu_indexes,
            },
          },
        }
      },
    },
  })

  await controller.handleSavedHostScan(1)
  controller.selectedGpuIndexes.value = [1]
  await controller.handleImport()

  assert.deepEqual(commitPayloads, [{ saved_host_id: 1, gpu_indexes: [1] }])
  assert.deepEqual(store.importContext.imported_gpu_indexes, [1])
  assert.deepEqual(router.replaced, ['/'])
})

test('retryable scan failure keeps saved host binding for direct retry', async () => {
  const controller = createImportWorkspaceController({
    router: createRouterStub(),
    store: createStoreStub(),
    auth: { currentUser: { role: 'admin' } },
    savedHosts: createSavedHostsStub([
      {
        id: 1,
        label: 'ssh',
        provider_type: 'ssh_linux',
        host: '10.151.225.108',
        port: 22,
        username: 'dell',
        auth_type: 'password',
        credential_status: 'ok',
      },
    ]),
    api: {
      getImportContext: async () => ({ data: { imported_gpu_indexes: [] } }),
      scanImportContext: async () => {
        const error = new Error('ssh connect failed')
        error.response = {
          data: {
            detail: 'Permission denied for user dell on host 10.151.225.108',
          },
        }
        throw error
      },
      commitImportContext: async () => ({ data: {} }),
    },
  })

  await controller.handleSavedHostScan(1)

  assert.equal(controller.selectedSavedHostId.value, 1)
  assert.equal(controller.activeStage.value, 'saved')
  assert.match(controller.feedback.value.text, /Permission denied/)
})

test('controller exposes saved host stage bindings expected by ImportWorkspace view', () => {
  const savedHosts = createSavedHostsStub([
    { id: 1, label: 'ssh' },
  ])
  const controller = createImportWorkspaceController({
    router: createRouterStub(),
    store: createStoreStub(),
    auth: { currentUser: { role: 'admin' } },
    savedHosts,
    api: {
      getImportContext: async () => ({ data: { imported_gpu_indexes: [] } }),
      scanImportContext: async () => ({ data: { success: false, gpus: [] } }),
      commitImportContext: async () => ({ data: {} }),
    },
  })

  assert.equal(controller.savedHostList, savedHosts.hosts)
  assert.equal(controller.savedHostLoading, savedHosts.loading)
  assert.equal(controller.savedHostErrorText, savedHosts.errorText)
  assert.equal(controller.savedHostScope, savedHosts.scope)
  assert.equal(controller.savedHostDeleteBusyId, savedHosts.deletingId)
})
