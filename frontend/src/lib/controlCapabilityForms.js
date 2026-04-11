const PRIORITY_OPTIONS = Object.freeze([{ label: '紧急', value: 'urgent' }, { label: '普通', value: 'normal' }, { label: '可延迟', value: 'deferrable' }])
const RULE_ROLE_OPTIONS = Object.freeze([{ label: '成员', value: 'member' }, { label: '受保护', value: 'protected' }, { label: '管理员', value: 'admin' }])
const TASK_KIND_OPTIONS = Object.freeze([{ label: '训练任务', value: 'training' }, { label: '推理服务', value: 'inference_service' }, { label: '交互会话', value: 'interactive_session' }, { label: '离线批处理', value: 'batch_compute' }, { label: '维护任务', value: 'maintenance' }])
const LIFECYCLE_OPTIONS = Object.freeze([{ label: 'Batch', value: 'batch' }, { label: 'Service', value: 'service' }, { label: 'Session', value: 'session' }])
const CHECKPOINT_POLICY_OPTIONS = Object.freeze([{ label: '无检查点', value: 'none' }, { label: '应用自管', value: 'app_managed' }])

const JOB_TASK_DEFAULTS = Object.freeze({
  training: { lifecycle_kind: 'batch', preemptible: true, checkpoint_policy: 'app_managed', restartable: true, latency_sensitive: false, exclusive_gpu: true },
  inference_service: { lifecycle_kind: 'service', preemptible: false, checkpoint_policy: 'none', restartable: false, latency_sensitive: true, exclusive_gpu: true },
  interactive_session: { lifecycle_kind: 'session', preemptible: false, checkpoint_policy: 'none', restartable: false, latency_sensitive: false, exclusive_gpu: true },
  batch_compute: { lifecycle_kind: 'batch', preemptible: true, checkpoint_policy: 'none', restartable: true, latency_sensitive: false, exclusive_gpu: false },
  maintenance: { lifecycle_kind: 'batch', preemptible: true, checkpoint_policy: 'none', restartable: false, latency_sensitive: false, exclusive_gpu: false },
})

function field(key, label, type, extra = {}) {
  return Object.freeze({ key, label, type, ...extra })
}

function cloneDefaultValue(value) {
  if (Array.isArray(value)) return [...value]
  if (value && typeof value === 'object') return { ...value }
  return value
}

function isBlank(value) {
  return value === '' || value === null || value === undefined
}

function readStringValue(value, label, required = true) {
  const normalized = String(value ?? '').trim()
  if (!normalized && required) {
    throw new Error(`${label}不能为空`)
  }
  return normalized || undefined
}

function readNumberValue(value, label, cast, required = true) {
  if (isBlank(value)) {
    if (required) throw new Error(`${label}不能为空`)
    return undefined
  }
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) {
    throw new Error(`${label}必须是数字`)
  }
  if (cast === 'int' && !Number.isInteger(numberValue)) {
    throw new Error(`${label}必须是整数`)
  }
  return cast === 'int' ? Math.trunc(numberValue) : numberValue
}

function serializeField(fieldDefinition, draft) {
  const value = draft?.[fieldDefinition.key]
  if (fieldDefinition.cast === 'boolean') return Boolean(value)
  if (fieldDefinition.cast === 'int' || fieldDefinition.cast === 'float') return readNumberValue(value, fieldDefinition.label, fieldDefinition.cast, fieldDefinition.required !== false)
  return readStringValue(value, fieldDefinition.label, fieldDefinition.required !== false)
}

function serializeSimpleDefinition(definition, draft) {
  return definition.fields.reduce((payload, item) => {
    const value = serializeField(item, draft)
    if (value !== undefined) {
      payload[item.argumentKey || item.key] = value
    }
    return payload
  }, {})
}

function buildResourceRequest(draft) {
  const resourceRequest = {}
  const gpu = readNumberValue(draft?.gpu, 'GPU 数量', 'int', false)
  const cpu = readNumberValue(draft?.cpu, 'CPU 核数', 'int', false)
  if (gpu !== undefined && gpu > 0) resourceRequest.gpu = gpu
  if (cpu !== undefined && cpu > 0) resourceRequest.cpu = cpu
  return resourceRequest
}

function parsePortList(value) {
  const items = Array.isArray(value) ? value : String(value ?? '').split(',')
  return items.map((item) => Number(String(item).trim())).filter(Number.isInteger)
}

function serializeJobSubmit(draft) {
  const taskKind = readStringValue(draft?.task_kind || 'training', '任务类型')
  const defaults = JOB_TASK_DEFAULTS[taskKind] || JOB_TASK_DEFAULTS.batch_compute
  const lifecycleKind = readStringValue(draft?.lifecycle_kind || defaults.lifecycle_kind, '生命周期')
  return {
    job_id: readStringValue(draft?.job_id, '作业 ID'),
    tenant_id: readStringValue(draft?.tenant_id, '租户'),
    project_id: readStringValue(draft?.project_id, '项目'),
    queue_id: readStringValue(draft?.queue_id, '队列'),
    submitter_id: readStringValue(draft?.submitter_id, '提交人'),
    job_type: lifecycleKind === 'service' ? 'service' : lifecycleKind === 'session' ? 'session' : 'batch',
    task_kind: taskKind,
    lifecycle_kind: lifecycleKind,
    entrypoint: readStringValue(draft?.entrypoint, '启动命令'),
    args: [],
    env: {},
    resource_request: buildResourceRequest(draft),
    placement_constraints: {},
    priority: readNumberValue(draft?.priority, '优先级', 'int', false) ?? 50,
    preemptible: Boolean(draft?.preemptible ?? defaults.preemptible),
    max_retries: readNumberValue(draft?.max_retries, '重试次数', 'int', false) ?? 0,
    timeout_seconds: readNumberValue(draft?.timeout_seconds, '超时时间', 'int', false) ?? 0,
    service_ports: parsePortList(draft?.service_ports),
    checkpoint_policy: readStringValue(draft?.checkpoint_policy || defaults.checkpoint_policy, '检查点策略'),
    runtime_profile: {
      expected_duration_seconds: readNumberValue(draft?.expected_duration_seconds, '预期时长', 'int', false) ?? 0,
      restartable: Boolean(draft?.restartable ?? defaults.restartable),
      latency_sensitive: Boolean(draft?.latency_sensitive ?? defaults.latency_sensitive),
      exclusive_gpu: Boolean(draft?.exclusive_gpu ?? defaults.exclusive_gpu),
    },
  }
}

const CAPABILITY_FORM_DEFINITIONS = Object.freeze({
  'runtime.snapshot.read': {
    kind: 'runtime.snapshot.read',
    fields: [],
  },
  'scheduler.power_limit.set': {
    kind: 'scheduler.power_limit.set',
    fields: [
      field('gpu_index', 'GPU 编号', 'number', { cast: 'int', defaultValue: 0 }),
      field('power_limit', '功耗上限(W)', 'number', { cast: 'int', defaultValue: 220 }),
    ],
  },
  'tasks.pause': {
    kind: 'tasks.pause',
    fields: [field('pid', 'PID', 'number', { cast: 'int', defaultValue: 0 })],
  },
  'tasks.resume': {
    kind: 'tasks.resume',
    fields: [field('pid', 'PID', 'number', { cast: 'int', defaultValue: 0 })],
  },
  'tasks.terminate': {
    kind: 'tasks.terminate',
    fields: [field('pid', 'PID', 'number', { cast: 'int', defaultValue: 0 })],
  },
  'tasks.priority.set': {
    kind: 'tasks.priority.set',
    fields: [
      field('pid', 'PID', 'number', { cast: 'int', defaultValue: 0 }),
      field('priority', '优先级', 'select', {
        cast: 'string',
        defaultValue: 'normal',
        options: PRIORITY_OPTIONS,
      }),
    ],
  },
  'scheduler.budget.configure': {
    kind: 'scheduler.budget.configure',
    fields: [
      field('enabled', '启用预算', 'toggle', { cast: 'boolean', defaultValue: true }),
      field('total_power_budget', '总功率预算(W)', 'number', {
        cast: 'int',
        defaultValue: 900,
      }),
    ],
  },
  'scheduler.auto.configure': {
    kind: 'scheduler.auto.configure',
    fields: [field('enabled', '启用自动调度', 'toggle', { cast: 'boolean', defaultValue: true })],
  },
  'scheduler.carbon_budget.configure': {
    kind: 'scheduler.carbon_budget.configure',
    fields: [
      field('enabled', '启用碳预算', 'toggle', { cast: 'boolean', defaultValue: true }),
      field('daily_budget_kg', '每日碳预算(kg)', 'number', {
        cast: 'float',
        defaultValue: 42,
      }),
    ],
  },
  'scheduler.run_once': {
    kind: 'scheduler.run_once',
    fields: [],
  },
  'job.submit': {
    kind: 'job.submit',
    fields: [
      field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' }),
      field('task_kind', '任务类型', 'select', { cast: 'string', defaultValue: 'training', options: TASK_KIND_OPTIONS }),
      field('lifecycle_kind', '生命周期', 'select', { cast: 'string', defaultValue: 'batch', options: LIFECYCLE_OPTIONS }),
      field('entrypoint', '启动命令', 'text', { cast: 'string', defaultValue: '' }),
      field('queue_id', '队列', 'text', { cast: 'string', defaultValue: 'default' }),
      field('tenant_id', '租户', 'text', { cast: 'string', defaultValue: '' }),
      field('project_id', '项目', 'text', { cast: 'string', defaultValue: '' }),
      field('submitter_id', '提交人', 'text', { cast: 'string', defaultValue: '' }),
      field('gpu', 'GPU 数量', 'number', { cast: 'int', defaultValue: 1, required: false }),
      field('cpu', 'CPU 核数', 'number', { cast: 'int', defaultValue: 4, required: false }),
      field('priority', '优先级', 'number', { cast: 'int', defaultValue: 50, required: false }),
      field('preemptible', '允许被抢占', 'toggle', { cast: 'boolean', defaultValue: true }),
      field('service_ports', '服务端口', 'text', { cast: 'string', defaultValue: '', required: false, placeholder: '8080,9090' }),
      field('checkpoint_policy', '检查点策略', 'select', { cast: 'string', defaultValue: 'app_managed', options: CHECKPOINT_POLICY_OPTIONS }),
      field('restartable', '可重启', 'toggle', { cast: 'boolean', defaultValue: true }),
      field('latency_sensitive', '延迟敏感', 'toggle', { cast: 'boolean', defaultValue: false }),
      field('exclusive_gpu', '独占 GPU', 'toggle', { cast: 'boolean', defaultValue: true }),
      field('expected_duration_seconds', '预期时长(s)', 'number', { cast: 'int', defaultValue: 0, required: false }),
      field('max_retries', '重试次数', 'number', { cast: 'int', defaultValue: 0, required: false }),
      field('timeout_seconds', '超时时间(s)', 'number', { cast: 'int', defaultValue: 0, required: false }),
    ],
    toArguments: serializeJobSubmit,
  },
  'job.list': {
    kind: 'job.list',
    fields: [],
  },
  'job.get': {
    kind: 'job.get',
    fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'policy.user_rule.upsert': {
    kind: 'policy.user_rule.upsert',
    fields: [
      field('username', '用户名', 'text', { cast: 'string', defaultValue: '' }),
      field('role', '治理角色', 'select', {
        cast: 'string',
        defaultValue: 'member',
        options: RULE_ROLE_OPTIONS,
      }),
      field('max_tasks', '最大任务数', 'number', { cast: 'int', defaultValue: 4 }),
      field('max_gpu_count', '最大 GPU 数', 'number', { cast: 'int', defaultValue: 1 }),
      field('max_memory_gb', '最大显存(GB)', 'number', { cast: 'float', defaultValue: 8 }),
      field('allow_preempt', '允许被抢占', 'toggle', { cast: 'boolean', defaultValue: true }),
      field('note', '备注', 'textarea', { cast: 'string', defaultValue: '', required: false }),
    ],
  },
  'policy.user_rule.delete': {
    kind: 'policy.user_rule.delete',
    fields: [field('username', '用户名', 'text', { cast: 'string', defaultValue: '' })],
  },
  'job.pause': {
    kind: 'job.pause',
    fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'job.resume': {
    kind: 'job.resume',
    fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'job.cancel': {
    kind: 'job.cancel',
    fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'job.requeue': {
    kind: 'job.requeue',
    fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'job.preempt': {
    kind: 'job.preempt',
    fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'job.checkpoint': {
    kind: 'job.checkpoint',
    fields: [
      field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' }),
      field('timeout_seconds', '检查点超时(s)', 'number', { cast: 'int', defaultValue: 30, required: false }),
    ],
  },
  'job.restore': {
    kind: 'job.restore',
    fields: [
      field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' }),
      field('checkpoint_id', '检查点 ID', 'text', { cast: 'string', defaultValue: '', required: false }),
    ],
  },
  'allocation.release': {
    kind: 'allocation.release',
    fields: [field('allocation_id', 'Allocation ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'node.drain': {
    kind: 'node.drain',
    fields: [field('node_id', '节点 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'node.undrain': {
    kind: 'node.undrain',
    fields: [field('node_id', '节点 ID', 'text', { cast: 'string', defaultValue: '' })],
  },
  'queue.status.read': {
    kind: 'queue.status.read',
    fields: [],
  },
})

export function getCapabilityFormDefinition(capabilityName) {
  const definition = CAPABILITY_FORM_DEFINITIONS[capabilityName]
  if (!definition) return null
  return { ...definition, fields: definition.fields.map((item) => ({ ...item })) }
}

export function buildCapabilityFormDraft(capabilityName) {
  const definition = getCapabilityFormDefinition(capabilityName)
  if (!definition) return {}
  return definition.fields.reduce((draft, item) => ({ ...draft, [item.key]: cloneDefaultValue(item.defaultValue ?? '') }), {})
}

export function buildCapabilityFormArguments(capabilityName, draft = {}) {
  const definition = getCapabilityFormDefinition(capabilityName)
  if (!definition) return { ...(draft || {}) }
  if (typeof definition.toArguments === 'function') return definition.toArguments({ ...(draft || {}) })
  return serializeSimpleDefinition(definition, draft)
}
