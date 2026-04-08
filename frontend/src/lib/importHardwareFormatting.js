const GIBIBYTE = 1024 * 1024 * 1024
const MEBIBYTE = 1024 * 1024

export function formatSystemMemoryBytes(value) {
  const total = Number(value || 0)
  if (!total) return '未知'
  if (total >= GIBIBYTE) return `${(total / GIBIBYTE).toFixed(1)} GB`
  return `${(total / MEBIBYTE).toFixed(0)} MB`
}

export function formatGpuMemoryBytes(value) {
  const total = Number(value || 0)
  if (!total) return '0 GB'
  if (total >= GIBIBYTE) return `${(total / GIBIBYTE).toFixed(1)} GB`
  return `${(total / MEBIBYTE).toFixed(0)} MB`
}
