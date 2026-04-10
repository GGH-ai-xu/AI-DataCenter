import { computed, ref } from 'vue'

import { getLlmConfig, testLlmConfig, updateLlmConfig } from '../services/api'

const DEFAULT_CONFIG = {
  enabled: false,
  base_url: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat',
  has_api_key: false,
  api_key_masked: '',
  updated_at: null,
  source: 'default',
  llm_available: false,
}

const DEFAULT_FORM = {
  enabled: false,
  base_url: 'https://api.deepseek.com/v1',
  model: '',
  api_key: '',
  keep_existing_key: true,
}

function buildPayload(form) {
  return {
    enabled: !!form.enabled,
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key: form.api_key.trim(),
    keep_existing_key: !!form.keep_existing_key,
  }
}

function normalizeSnapshot(snapshot) {
  return {
    enabled: !!snapshot?.enabled,
    base_url: snapshot?.base_url || DEFAULT_CONFIG.base_url,
    model: snapshot?.model || '',
    has_api_key: !!snapshot?.has_api_key,
    api_key_masked: snapshot?.api_key_masked || '',
    updated_at: snapshot?.updated_at || null,
    source: snapshot?.source || 'default',
    llm_available: !!snapshot?.llm_available,
  }
}

export function useAiAssistantLlm() {
  const llmBusy = ref(false)
  const llmReady = ref(false)
  const llmNotice = ref('')
  const llmFeedback = ref(null)
  const llmConfig = ref({ ...DEFAULT_CONFIG })
  const llmForm = ref({ ...DEFAULT_FORM })

  const hasStoredKey = computed(() => !!llmConfig.value.has_api_key)
  const savedKeyHint = computed(() => (
    hasStoredKey.value
      ? `已保存 Key：${llmConfig.value.api_key_masked || '******'}`
      : '当前未保存 API Key'
  ))
  const canTestLlm = computed(() => (
    !!llmForm.value.base_url.trim()
    && (!!llmForm.value.api_key.trim() || !!llmForm.value.keep_existing_key)
  ))
  const canSaveLlm = computed(() => (
    !!llmForm.value.base_url.trim()
    && (!llmForm.value.enabled || !!llmForm.value.api_key.trim() || !!llmForm.value.keep_existing_key)
  ))
  const llmSourceLabel = computed(() => (
    { runtime: '页面运行时', env: '环境变量' }[llmConfig.value.source] || '默认值'
  ))
  const llmUpdatedAt = computed(() => {
    const ts = Number(llmConfig.value.updated_at || 0)
    if (!ts) return '未保存'
    return new Date(ts * 1000).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  })

  function applySnapshot(snapshot) {
    const nextSnapshot = normalizeSnapshot(snapshot)
    llmConfig.value = nextSnapshot
    llmForm.value = {
      enabled: nextSnapshot.enabled,
      base_url: nextSnapshot.base_url,
      model: nextSnapshot.model,
      api_key: '',
      keep_existing_key: nextSnapshot.has_api_key,
    }
    llmReady.value = !!nextSnapshot.llm_available
    llmNotice.value = llmReady.value ? '' : (
      !nextSnapshot.enabled
        ? 'AI 对话助手当前已关闭。执行请求仍可走规则解析或 runtime。'
        : (!nextSnapshot.has_api_key
          ? '缺少 API Key。填写后先测试连接，再保存并生效。'
          : 'AI 对话助手尚未就绪，请先检查当前 LLM 配置。')
    )
  }

  async function loadAssistantCapability() {
    llmBusy.value = true
    try {
      const { data } = await getLlmConfig()
      applySnapshot(data)
    } catch {
      llmReady.value = false
      llmNotice.value = '当前无法读取 AI 配置，请先检查后端服务是否正常。'
    } finally {
      llmBusy.value = false
    }
  }

  async function runLlmTest() {
    if (llmBusy.value || !canTestLlm.value) return
    llmBusy.value = true
    llmFeedback.value = null
    try {
      const { data } = await testLlmConfig(buildPayload(llmForm.value))
      if (!llmForm.value.model.trim() && data?.llm?.model) {
        llmForm.value.model = data.llm.model
      }
      llmFeedback.value = {
        type: 'success',
        text: `连接测试成功，当前模型：${data?.llm?.model || llmForm.value.model || '未识别'}`,
      }
    } catch (error) {
      llmFeedback.value = {
        type: 'error',
        text: error?.response?.data?.detail || 'LLM 连接测试失败，请检查地址、模型和密钥。',
      }
    } finally {
      llmBusy.value = false
    }
  }

  async function saveLlmConfig() {
    if (llmBusy.value || !canSaveLlm.value) return
    llmBusy.value = true
    llmFeedback.value = null
    try {
      const { data } = await updateLlmConfig(buildPayload(llmForm.value))
      applySnapshot(data?.llm || {})
      llmFeedback.value = {
        type: 'success',
        text: data?.message || 'AI 助手配置已保存。',
      }
    } catch (error) {
      llmFeedback.value = {
        type: 'error',
        text: error?.response?.data?.detail || 'LLM 配置保存失败。',
      }
    } finally {
      llmBusy.value = false
    }
  }

  return {
    llmBusy,
    llmReady,
    llmNotice,
    llmFeedback,
    llmConfig,
    llmForm,
    hasStoredKey,
    savedKeyHint,
    canTestLlm,
    canSaveLlm,
    llmSourceLabel,
    llmUpdatedAt,
    loadAssistantCapability,
    runLlmTest,
    saveLlmConfig,
  }
}
