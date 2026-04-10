const GIBIBYTE = 1024 * 1024 * 1024
const MEBIBYTE = 1024 * 1024

export function formatSystemMemoryBytes(value) {
  const total = Number(value || 0)
  if (!total) return '未知'
  if (total >= GIBIBYTE) return `${(total / GIBIBYTE).toFixed(1)} GB`
  return `${(total / MEBIBYTE).toFixed(0)} MB`
}

export function normalizeGpuMemoryBytes(value) {
  const total = Number(value || 0)
  if (!total) return 0
  if (total < MEBIBYTE) return total * MEBIBYTE
  return total
}

export function formatGpuMemoryBytes(value) {
  const total = normalizeGpuMemoryBytes(value)
  if (!total) return '0 GB'
  if (total >= GIBIBYTE) return `${(total / GIBIBYTE).toFixed(1)} GB`
  return `${(total / MEBIBYTE).toFixed(0)} MB`
}

export function formatGpuMemoryGiB(value) {
  const total = normalizeGpuMemoryBytes(value)
  return (total / GIBIBYTE).toFixed(1)
}

export function gpuMemoryUsagePercent(used, total) {
  const normalizedTotal = normalizeGpuMemoryBytes(total)
  if (!normalizedTotal) return 0
  const normalizedUsed = normalizeGpuMemoryBytes(used)
  return Math.min(100, Math.round((normalizedUsed / normalizedTotal) * 100))
}
