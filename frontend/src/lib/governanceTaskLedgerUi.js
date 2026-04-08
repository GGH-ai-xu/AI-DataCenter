function normalizePid(pid) {
  const normalized = Number(pid)
  return Number.isFinite(normalized) ? normalized : null
}

export function toggleExpandedPid(currentPid, nextPid) {
  const current = normalizePid(currentPid)
  const next = normalizePid(nextPid)

  if (next === null) {
    return current
  }

  return current === next ? null : next
}

export function syncExpandedPid(expandedPid, processes = []) {
  const current = normalizePid(expandedPid)

  if (current === null) {
    return null
  }

  const visible = processes.some((proc) => normalizePid(proc?.pid) === current)
  return visible ? current : null
}
