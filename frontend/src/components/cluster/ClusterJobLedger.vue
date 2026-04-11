<script setup>
import { reactive } from 'vue'

import {
  availableJobActions,
  jobActionLabel,
} from '../../lib/clusterConsoleActions.js'
import {
  buildCapabilityFormArguments,
  buildCapabilityFormDraft,
} from '../../lib/controlCapabilityModels.js'

const props = defineProps({
  jobs: {
    type: Array,
    default: () => [],
  },
  submitterId: {
    type: String,
    default: 'console-user',
  },
  submitBusy: {
    type: Boolean,
    default: false,
  },
  actionBusy: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['submit', 'action'])

const form = reactive(buildCapabilityFormDraft('job.submit'))
form.entrypoint = form.entrypoint || 'python train.py'

function submitJob() {
  emit('submit', buildCapabilityFormArguments('job.submit', {
    ...form,
    submitter_id: props.submitterId || form.submitter_id || 'console-user',
  }))
}

function actionBusyKey(jobId, action) {
  return `${jobId}:${action}`
}

function isActionBusy(jobId, action) {
  return Boolean(props.actionBusy?.[actionBusyKey(jobId, action)])
}

function statusBadgeClass(job) {
  if (job.status === 'running' || job.status === 'succeeded') return 'status-badge--ok'
  if (job.status === 'failed') return 'status-badge--critical'
  return 'status-badge--warning'
}

function emitAction(job, action) {
  emit('action', { jobId: job.id, action, status: job.status })
}
</script>

<template>
  <section class="tech-card cluster-job-ledger">
    <div class="cluster-section-heading">
      <h3>作业账本</h3>
      <p>统一提交训练、推理服务、交互会话、批处理与维护任务，下方紧凑展示受管作业。</p>
    </div>

    <form class="cluster-job-ledger__form" @submit.prevent="submitJob">
      <input v-model="form.job_id" type="text" placeholder="job-id" />
      <select v-model="form.task_kind">
        <option value="training">训练任务</option>
        <option value="inference_service">推理服务</option>
        <option value="interactive_session">交互会话</option>
        <option value="batch_compute">离线批处理</option>
        <option value="maintenance">维护任务</option>
      </select>
      <select v-model="form.lifecycle_kind">
        <option value="batch">Batch</option>
        <option value="service">Service</option>
        <option value="session">Session</option>
      </select>
      <input v-model="form.entrypoint" type="text" placeholder="python train.py" />
      <input v-model.number="form.gpu" type="number" min="0" step="1" placeholder="GPU" />
      <input v-model.number="form.cpu" type="number" min="0" step="1" placeholder="CPU" />
      <input v-model="form.service_ports" type="text" placeholder="端口 8080,9090" />
      <button class="cluster-job-ledger__submit" type="submit" :disabled="submitBusy || !form.job_id.trim() || !form.entrypoint.trim()">
        {{ submitBusy ? '提交中...' : '提交作业' }}
      </button>
    </form>

    <div class="cluster-job-ledger__rows">
      <article
        v-for="job in props.jobs"
        :key="job.id"
        class="cluster-job-row"
      >
        <div class="cluster-job-row__primary">
          <strong>{{ job.id }}</strong>
          <span class="cluster-job-row__kind">{{ job.taskKind }}</span>
          <span class="cluster-job-row__kind">{{ job.lifecycleKind }}</span>
          <span v-if="job.readinessState" class="cluster-job-row__kind">{{ job.readinessState }}</span>
        </div>
        <div class="cluster-job-row__secondary">
          <span class="cluster-job-row__command">{{ job.entrypoint }}</span>
        </div>
        <div class="cluster-job-row__secondary">
          <span class="status-badge" :class="statusBadgeClass(job)">
            {{ job.status }}
          </span>
          <span>队列 {{ job.queueId }}</span>
          <span>优先级 {{ job.priority }}</span>
          <span>{{ job.submitter || 'unknown' }}</span>
          <span v-if="job.servicePorts?.length">端口 {{ job.servicePorts.join(', ') }}</span>
        </div>
        <div v-if="job.runtimeJobHandle" class="cluster-job-row__reason">
          <span>运行句柄</span>
          <span>{{ job.runtimeJobHandle }}</span>
        </div>
        <div v-if="job.checkpointStatus" class="cluster-job-row__reason">
          <span>检查点</span>
          <span>{{ job.checkpointId || '最近一次' }} · {{ job.checkpointStatus }}</span>
        </div>
        <div v-if="job.awaitingRelease" class="cluster-job-row__reason">
          <span>资源回收</span>
          <span>allocation 正在 releasing，等待下一轮推进。</span>
        </div>
        <div v-if="job.planReason" class="cluster-job-row__reason">
          <span>{{ job.planType === 'reject' ? '拒绝原因' : '等待原因' }}</span>
          <span>{{ job.planReason }}</span>
        </div>
        <div v-if="job.lastError" class="cluster-job-row__reason cluster-job-row__reason--error">
          <span>调度失败</span>
          <span>{{ job.lastError }}</span>
        </div>
        <div v-if="availableJobActions(job).length" class="cluster-job-row__actions">
          <button
            v-for="action in availableJobActions(job)"
            :key="`${job.id}-${action}`"
            type="button"
            class="cluster-job-row__action"
            :disabled="isActionBusy(job.id, action)"
            @click="emitAction(job, action)"
          >
            {{ isActionBusy(job.id, action) ? '处理中...' : jobActionLabel(action) }}
          </button>
        </div>
      </article>
      <div v-if="!props.jobs.length" class="cluster-job-ledger__empty">
        还没有受管作业，可先提交一个训练任务、推理服务或交互会话。
      </div>
    </div>
  </section>
</template>

<style scoped>
.cluster-job-ledger {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.cluster-job-ledger__form {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(120px, 0.9fr) minmax(100px, 0.8fr) minmax(0, 2fr) repeat(2, minmax(68px, 92px)) minmax(0, 1fr) auto;
  gap: 10px;
}

.cluster-job-ledger__form input,
.cluster-job-ledger__form select {
  min-width: 0;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
  background: var(--field-background);
  color: var(--text-primary);
}

.cluster-job-ledger__submit {
  padding: 10px 14px;
  border: none;
  border-radius: 12px;
  background: var(--state-ok-bg);
  color: var(--state-ok-text);
  font-weight: 700;
  cursor: pointer;
}

.cluster-job-ledger__rows {
  display: grid;
  gap: 10px;
}

.cluster-job-row {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
}

.cluster-job-row__primary,
.cluster-job-row__secondary,
.cluster-job-row__reason {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.cluster-job-row__command,
.cluster-job-row__secondary,
.cluster-job-row__reason {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.cluster-job-row__kind {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: 0.74rem;
}

.cluster-job-row__reason--error {
  color: var(--state-danger-text, #d94c4c);
}

.cluster-job-row__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.cluster-job-row__action {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  color: var(--text-primary);
}

.cluster-job-row__action:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.cluster-job-ledger__empty {
  padding: 16px;
  border-radius: 14px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.84rem;
}

@media (max-width: 1024px) {
  .cluster-job-ledger__form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
