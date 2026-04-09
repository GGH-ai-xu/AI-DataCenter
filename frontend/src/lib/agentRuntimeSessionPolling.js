const TERMINAL_STATUSES = new Set(['completed', 'failed', 'aborted'])

export function createAgentRuntimeSessionPolling({
  scheduler = globalThis,
  intervalMs = 2000,
} = {}) {
  let timerId = null

  function stop() {
    if (!timerId) return
    scheduler.clearInterval(timerId)
    timerId = null
  }

  function start(refresh) {
    stop()
    timerId = scheduler.setInterval(async () => {
      const session = await refresh()
      if (TERMINAL_STATUSES.has(session?.status)) {
        stop()
      }
    }, intervalMs)
  }

  return { start, stop }
}
