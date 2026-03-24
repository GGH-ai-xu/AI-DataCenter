<script setup>
/**
 * TaskManager.vue - 任务管理页
 * 查看GPU进程，支持暂停/恢复/终止，设置优先级
 */
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/app'
import { pauseTask, resumeTask, terminateTask, setTaskPriority } from '../services/api'

const store = useAppStore()
const actionLoading = ref({})

const fmtMem = (bytes) => ((bytes || 0) / 1048576).toFixed(0) + ' MB'

const priorityColors = {
  urgent: { bg: 'rgba(248,113,113,0.12)', color: '#f87171', label: '紧急' },
  normal: { bg: 'rgba(56,189,248,0.12)', color: '#38bdf8', label: '普通' },
  deferrable: { bg: 'rgba(148,163,184,0.12)', color: '#94a3b8', label: '可延迟' },
}

async function doAction(pid, action) {
  actionLoading.value[`${pid}-${action}`] = true
  try {
    if (action === 'pause') await pauseTask(pid)
    else if (action === 'resume') await resumeTask(pid)
    else if (action === 'terminate') await terminateTask(pid)
  } catch (e) {
    console.error(e)
  }
  actionLoading.value[`${pid}-${action}`] = false
}

async function changePriority(pid, priority) {
  try {
    await setTaskPriority(pid, priority)
  } catch (e) {
    console.error(e)
  }
}
</script>

<template>
  <div class="task-page">
    <div class="section-title" style="margin-bottom: 16px; font-size: 1rem">GPU 进程管理</div>

    <div class="task-table tech-card">
      <table>
        <thead>
          <tr>
            <th>PID</th>
            <th>GPU</th>
            <th>进程名</th>
            <th>用户</th>
            <th>GPU显存</th>
            <th>CPU</th>
            <th>优先级</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="proc in store.processes" :key="proc.pid">
            <td class="stat-value" style="color: var(--accent-primary)">{{ proc.pid }}</td>
            <td><span class="gpu-tag">GPU {{ proc.gpu_index }}</span></td>
            <td style="max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ proc.name }}</td>
            <td style="color: var(--text-muted)">{{ proc.username }}</td>
            <td class="stat-value">{{ fmtMem(proc.gpu_memory_used) }}</td>
            <td class="stat-value">{{ proc.cpu_percent?.toFixed(1) }}%</td>
            <td>
              <select
                class="priority-select"
                :value="proc.priority || 'normal'"
                @change="changePriority(proc.pid, $event.target.value)"
                :style="{ color: priorityColors[proc.priority || 'normal'].color, background: priorityColors[proc.priority || 'normal'].bg }"
              >
                <option value="urgent">紧急</option>
                <option value="normal">普通</option>
                <option value="deferrable">可延迟</option>
              </select>
            </td>
            <td>
              <div style="display: flex; gap: 6px">
                <button class="btn-tech" style="padding: 4px 10px; font-size: 0.75rem" @click="doAction(proc.pid, 'pause')">暂停</button>
                <button class="btn-tech" style="padding: 4px 10px; font-size: 0.75rem" @click="doAction(proc.pid, 'resume')">恢复</button>
                <button class="btn-tech btn-tech--danger" style="padding: 4px 10px; font-size: 0.75rem" @click="doAction(proc.pid, 'terminate')">终止</button>
              </div>
            </td>
          </tr>
          <tr v-if="!store.processes.length">
            <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px">暂无GPU进程</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.task-page { max-width: 1400px; margin: 0 auto; }

.task-table { overflow-x: auto; }

table { width: 100%; border-collapse: collapse; }

th {
  text-align: left;
  padding: 12px 16px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-color);
}

td {
  padding: 12px 16px;
  font-size: 0.8125rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

tr:hover td { background: rgba(56, 189, 248, 0.03); }

.gpu-tag {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--accent-primary);
  background: rgba(56, 189, 248, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.priority-select {
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  font-size: 0.75rem;
  cursor: pointer;
  outline: none;
}
</style>
