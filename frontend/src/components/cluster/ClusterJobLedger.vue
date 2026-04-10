<script setup>
import { reactive } from 'vue'

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
})

const emit = defineEmits(['submit'])

const form = reactive({
  jobId: '',
  entrypoint: 'python train.py',
  gpu: 1,
  cpu: 4,
})

function submitJob() {
  emit('submit', {
    job_id: form.jobId.trim(),
    tenant_id: 'default',
    project_id: 'interactive',
    queue_id: 'default',
    submitter_id: props.submitterId || 'console-user',
    job_type: 'batch',
    entrypoint: form.entrypoint.trim(),
    args: [],
    env: {},
    resource_request: {
      gpu: Number(form.gpu),
      cpu: Number(form.cpu),
    },
    placement_constraints: {},
    priority: 50,
    preemptible: true,
    max_retries: 0,
    timeout_seconds: 0,
  })
}
</script>

<template>
  <section class="tech-card cluster-job-ledger">
    <div class="cluster-section-heading">
      <h3>作业账本</h3>
      <p>上方直接提交最小 JobSpec，下方紧凑展示已提交作业。</p>
    </div>

    <form class="cluster-job-ledger__form" @submit.prevent="submitJob">
      <input v-model="form.jobId" type="text" placeholder="job-id" />
      <input v-model="form.entrypoint" type="text" placeholder="python train.py" />
      <input v-model.number="form.gpu" type="number" min="0" step="1" />
      <input v-model.number="form.cpu" type="number" min="0" step="1" />
      <button class="cluster-job-ledger__submit" type="submit" :disabled="submitBusy || !form.jobId.trim() || !form.entrypoint.trim()">
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
          <span class="cluster-job-row__command">{{ job.entrypoint }}</span>
        </div>
        <div class="cluster-job-row__secondary">
          <span class="status-badge" :class="job.status === 'running' ? 'status-badge--ok' : 'status-badge--warning'">
            {{ job.status }}
          </span>
          <span>队列 {{ job.queueId }}</span>
          <span>优先级 {{ job.priority }}</span>
          <span>{{ job.submitter || 'unknown' }}</span>
        </div>
      </article>
      <div v-if="!props.jobs.length" class="cluster-job-ledger__empty">
        还没有作业，先提交一个最小训练任务试试。
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
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 2fr) repeat(2, minmax(68px, 92px)) auto;
  gap: 10px;
}

.cluster-job-ledger__form input {
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
.cluster-job-row__secondary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.cluster-job-row__command,
.cluster-job-row__secondary {
  font-size: 0.8rem;
  color: var(--text-secondary);
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
