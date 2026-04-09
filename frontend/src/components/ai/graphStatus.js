export function getGraphConnectionStatus(summary = {}) {
  if (!summary.configured) {
    return '未配置'
  }
  if (!summary.dependency_installed) {
    return '缺少驱动'
  }
  if (!summary.neo4j_connected) {
    return '未连接'
  }
  return '可写入'
}

export function getGraphGenerateDisabledReason(options = {}) {
  const form = options.form || {}
  if (options.busy) {
    return '当前还有图谱任务在执行，请稍候。'
  }
  if (!options.llmReady) {
    return 'LLM 未就绪，暂时无法生成图谱草稿。'
  }
  if (!String(form.title || '').trim()) {
    return '请先填写论文标题。'
  }
  if (!String(form.abstract || '').trim() && !String(form.content || '').trim()) {
    return '至少提供摘要或正文片段，才能生成图谱草稿。'
  }
  return ''
}

export function getGraphExecuteDisabledReason(options = {}) {
  const summary = options.summary || {}
  const draftResult = options.draftResult || null
  if (options.busy) {
    return '当前还有图谱任务在执行，请稍候。'
  }
  if (!draftResult?.graph?.nodes?.length) {
    return '请先生成图谱草稿。'
  }
  if (!summary.neo4j_connected) {
    return summary.message || 'Neo4j 未连接，暂时无法写入图库。'
  }
  return ''
}

export function getGraphRecoveryHint(summary = {}) {
  if (summary.neo4j_connected) {
    return 'Neo4j 已在线，可直接写入图库。'
  }
  if (summary.local_start_available) {
    return summary.local_start_message || summary.message || '可尝试一键启动本地 Neo4j。'
  }
  return summary.local_start_message || summary.message || '当前环境不支持一键拉起本地 Neo4j。'
}
