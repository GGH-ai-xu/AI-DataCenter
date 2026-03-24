/**
 * Mock数据生成器 - 无GPU服务器时模拟4卡RTX 3090数据
 * 在开发/演示时使用，让大屏有真实感的动态数据
 */

function rand(min, max) {
  return Math.random() * (max - min) + min
}

function randInt(min, max) {
  return Math.floor(rand(min, max + 1))
}

const GPU_NAMES = [
  'NVIDIA GeForce RTX 3090',
  'NVIDIA GeForce RTX 3090',
  'NVIDIA GeForce RTX 3090',
  'NVIDIA GeForce RTX 3090',
]

// 每张GPU的基准负载（模拟不同任务场景）
const BASE_PROFILES = [
  { util: 85, power: 280, temp: 72, mem_pct: 0.78 }, // GPU0: 训练大模型
  { util: 45, power: 180, temp: 58, mem_pct: 0.42 }, // GPU1: 推理服务
  { util: 92, power: 310, temp: 78, mem_pct: 0.91 }, // GPU2: 训练中
  { util: 15, power: 90, temp: 42, mem_pct: 0.12 },  // GPU3: 空闲
]

const MEM_TOTAL = 24 * 1024 * 1024 * 1024 // 24GB

export function generateMockGpus() {
  return BASE_PROFILES.map((base, i) => {
    const util = Math.max(0, Math.min(100, base.util + randInt(-8, 8)))
    const power = Math.max(50, Math.min(350, base.power + rand(-15, 15)))
    const temp = Math.max(30, Math.min(95, base.temp + randInt(-3, 3)))
    const memUsed = Math.floor(MEM_TOTAL * Math.max(0.05, Math.min(0.98, base.mem_pct + rand(-0.03, 0.03))))

    return {
      index: i,
      name: GPU_NAMES[i],
      temperature: temp,
      power_usage: Math.round(power * 10) / 10,
      power_limit: 350,
      gpu_utilization: util,
      memory_utilization: Math.round(memUsed / MEM_TOTAL * 100),
      memory_used: memUsed,
      memory_total: MEM_TOTAL,
      memory_free: MEM_TOTAL - memUsed,
      fan_speed: Math.max(30, Math.min(100, Math.round(temp * 1.1 + randInt(-5, 5)))),
      clock_sm: randInt(1200, 1800),
      clock_mem: randInt(9000, 9800),
      timestamp: Date.now() / 1000,
    }
  })
}

export function generateMockSystem() {
  return {
    cpu_percent: rand(15, 65),
    cpu_count: 32,
    memory_total: 128 * 1024 * 1024 * 1024,
    memory_used: Math.floor(128 * 1024 * 1024 * 1024 * rand(0.3, 0.6)),
    memory_percent: rand(30, 60),
    timestamp: Date.now() / 1000,
  }
}

export function generateMockProcesses() {
  return [
    { pid: 12481, gpu_index: 0, gpu_memory_used: 18 * 1024 * 1024 * 1024, name: 'python', username: 'researcher', command: 'python train_llm.py --model gpt2-xl', cpu_percent: 45.2, create_time: Date.now() / 1000 - 7200, priority: 'urgent' },
    { pid: 13302, gpu_index: 1, gpu_memory_used: 9.5 * 1024 * 1024 * 1024, name: 'python', username: 'api-server', command: 'python serve.py --port 8080', cpu_percent: 12.8, create_time: Date.now() / 1000 - 86400, priority: 'normal' },
    { pid: 14156, gpu_index: 2, gpu_memory_used: 21 * 1024 * 1024 * 1024, name: 'python', username: 'researcher', command: 'python finetune.py --dataset alpaca', cpu_percent: 62.1, create_time: Date.now() / 1000 - 3600, priority: 'normal' },
    { pid: 15789, gpu_index: 3, gpu_memory_used: 2.5 * 1024 * 1024 * 1024, name: 'python', username: 'student', command: 'python test_inference.py', cpu_percent: 3.4, create_time: Date.now() / 1000 - 600, priority: 'deferrable' },
  ]
}

export function generateMockAlerts() {
  const now = Date.now() / 1000
  const alerts = []
  // 随机产生告警
  if (Math.random() > 0.7) {
    alerts.push({
      gpu_index: 2,
      alert_type: 'temperature',
      severity: 'warning',
      message: 'GPU2 温度偏高: 78°C (阈值85°C)',
      value: 78,
      threshold: 85,
      timestamp: now,
    })
  }
  if (Math.random() > 0.85) {
    alerts.push({
      gpu_index: 0,
      alert_type: 'power',
      severity: 'warning',
      message: 'GPU0 功耗较高: 295W (阈值320W)',
      value: 295,
      threshold: 320,
      timestamp: now,
    })
  }
  return alerts
}
