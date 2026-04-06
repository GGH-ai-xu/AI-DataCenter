/**
 * WebSocket连接管理 - 接收实时GPU数据推送
 */
import { ref, onUnmounted } from 'vue'

const INITIAL_RETRY_DELAY = 1000
const MAX_RETRY_DELAY = 30000

function buildWebSocketUrl(token) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const search = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${protocol}//${location.host}/ws${search}`
}

export function useWebSocket(options = {}) {
  const onRealtimeMessage = options.onRealtimeMessage
  const onConnectionChange = options.onConnectionChange
  const getToken = options.getToken || (() => '')
  const shouldReconnect = options.shouldReconnect || (() => true)
  const connected = ref(false)
  let socket = null
  let reconnectTimer = null
  let reconnectDelay = INITIAL_RETRY_DELAY
  let manualDisconnect = false

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function notifyConnectionChange(nextState) {
    connected.value = nextState
    if (onConnectionChange) {
      onConnectionChange(nextState)
    }
  }

  function connect() {
    const token = String(getToken() || '').trim()
    if (!token) {
      manualDisconnect = true
      notifyConnectionChange(false)
      return
    }
    manualDisconnect = false
    socket = new WebSocket(buildWebSocketUrl(token))

    socket.onopen = () => {
      clearReconnectTimer()
      reconnectDelay = INITIAL_RETRY_DELAY
      notifyConnectionChange(true)
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'realtime' || data.type === 'runtime') {
          onRealtimeMessage?.(data)
        }
      } catch {}
    }

    socket.onclose = () => {
      notifyConnectionChange(false)
      if (manualDisconnect || !shouldReconnect()) {
        return
      }
      clearReconnectTimer()
      reconnectTimer = setTimeout(connect, reconnectDelay)
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RETRY_DELAY)
    }

    socket.onerror = () => {
      socket?.close()
    }
  }

  function disconnect() {
    manualDisconnect = true
    clearReconnectTimer()
    notifyConnectionChange(false)
    socket?.close()
    socket = null
  }

  onUnmounted(disconnect)

  return {
    connected,
    connect,
    disconnect,
  }
}
