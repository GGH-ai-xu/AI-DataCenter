import { computed, reactive } from 'vue'

import {
  approveControlCommand,
  createControlCommand,
  getControlCapabilities,
  getControlCommand,
  listControlCommands,
} from '../services/api.js'
import {
  buildCapabilityDrawerModel,
  buildControlCommandTimeline,
} from '../lib/controlCapabilityModels.js'

const DEFAULT_SECTION = 'actions'

function activeSectionValue(activeSection) {
  return activeSection?.value || activeSection || DEFAULT_SECTION
}

function defaultSourcePage(section) {
  if (section === 'cluster') return 'governance-cluster'
  if (section === 'policies') return 'governance-policies'
  if (section === 'review') return 'governance-review'
  return 'governance-actions'
}

export function useGovernanceControlPlane(options = {}) {
  const drawer = reactive({
    open: false,
    section: DEFAULT_SECTION,
    capabilities: [],
    items: [],
    loading: false,
    submitting: false,
    selectedName: '',
    latestCommand: null,
    error: '',
  })
  const ledger = reactive({
    loading: false,
    items: [],
    error: '',
  })

  function syncDrawer(section = activeSectionValue(options.activeSection)) {
    drawer.section = section
    drawer.items = buildCapabilityDrawerModel(drawer.capabilities, section).items
    if (!drawer.selectedName && drawer.items.length) {
      drawer.selectedName = drawer.items[0].name
    }
  }

  async function loadCapabilities() {
    drawer.loading = true
    drawer.error = ''
    try {
      const { data } = await getControlCapabilities()
      drawer.capabilities = data?.capabilities || []
      syncDrawer()
    } catch (error) {
      drawer.error = error?.message || '加载能力目录失败'
      throw error
    } finally {
      drawer.loading = false
    }
  }

  async function refreshCommands(limit = 50) {
    ledger.loading = true
    ledger.error = ''
    try {
      const { data } = await listControlCommands(limit)
      ledger.items = buildControlCommandTimeline(data?.commands || [])
      return ledger.items
    } catch (error) {
      ledger.error = error?.message || '加载命令账本失败'
      throw error
    } finally {
      ledger.loading = false
    }
  }

  async function submitCommand(payload) {
    drawer.submitting = true
    drawer.error = ''
    try {
      const { data } = await createControlCommand(payload)
      drawer.latestCommand = data || null
      await refreshCommands()
      return data
    } catch (error) {
      drawer.error = error?.message || '提交命令失败'
      throw error
    } finally {
      drawer.submitting = false
    }
  }

  async function submitBuiltinCommand(capabilityName, argumentsPayload, options = {}) {
    const section = options.section || drawer.section || activeSectionValue(options.activeSection)
    const command = await submitCommand({
      capability_name: capabilityName,
      arguments: argumentsPayload,
      acknowledge_risk: Boolean(options.acknowledgeRisk),
      reason: options.reason || '',
      source_page: options.sourcePage || defaultSourcePage(section),
    })
    if (command?.execution_state === 'failed') {
      throw new Error(command.error_message || command.result_summary || '命令执行失败')
    }
    return command
  }

  async function reloadCommand(commandId) {
    const { data } = await getControlCommand(commandId)
    drawer.latestCommand = data || null
    return data
  }

  async function approveCommand(commandId, approved, comment = '') {
    const { data } = await approveControlCommand(commandId, approved, comment)
    drawer.latestCommand = data || null
    await refreshCommands()
    return data
  }

  async function openDrawer(section = activeSectionValue(options.activeSection)) {
    drawer.open = true
    syncDrawer(section)
    if (!drawer.capabilities.length) {
      await loadCapabilities()
    }
  }

  function closeDrawer() {
    drawer.open = false
    drawer.error = ''
  }

  return {
    drawer,
    ledger,
    drawerModel: computed(() =>
      buildCapabilityDrawerModel(drawer.capabilities, drawer.section)
    ),
    loadCapabilities,
    refreshCommands,
    submitCommand,
    submitBuiltinCommand,
    reloadCommand,
    approveCommand,
    openDrawer,
    closeDrawer,
  }
}
