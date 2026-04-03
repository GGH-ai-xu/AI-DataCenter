function normalizeIndexes(indexes = []) {
  return [...new Set((indexes || []).map((value) => Number(value)).filter(Number.isInteger))]
    .sort((left, right) => left - right)
}

export function hasValidImportContext(context) {
  return Boolean(context?.valid) && normalizeIndexes(context?.imported_gpu_indexes).length > 0
}

export function formatImportedGpuLabel(indexes = []) {
  const count = normalizeIndexes(indexes).length
  return count > 0 ? `已导入 ${count} 张卡` : '未导入 GPU'
}

export function formatImportSourceLabel(context) {
  const providerType = context?.provider_type || context?.providerType || ''
  if (providerType === 'ssh_linux') return 'SSH Linux 导入模式'
  if (providerType === 'http_remote') return '远程 Agent 导入模式'
  if (providerType === 'http_local') return '本机 Agent 导入模式'
  return '导入模式待识别'
}
