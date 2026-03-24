/**
 * WebSocket连接管理 - 接收实时GPU数据推送
 */
import { ref, onUnmounted } from 'vue'

export function useWebSocket() {
  const connected = ref(false)
  const gpuData = ref([])
  const systemData = ref(null)
  const processData = ref([])
  const realtimeAlerts = ref([])
  let ws = null
  let reconnectTimer = null

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws`

    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      // 心跳
      if (reconnectTimer) clearInterval(reconnectTimer)
      reconnectTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 30000)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'realtime') {
          gpuData.value = data.gpus || []
          systemData.value = data.system || null
          processData.value = data.processes || []
          if (data.alerts?.length) {
            realtimeAlerts.value = [...data.alerts, ...realtimeAlerts.value].slice(0, 50)
          }
        }
      } catch (e) {
        // pong或其他非JSON消息
      }
    }

    ws.onclose = () => {
      connected.value = false
      if (reconnectTimer) clearInterval(reconnectTimer)
      // 3秒后重连
      setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    if (reconnectTimer) clearInterval(reconnectTimer)
    ws?.close()
    ws = null
  }

  onUnmounted(disconnect)

  return {
    connected,
    gpuData,
    systemData,
    processData,
    realtimeAlerts,
    connect,
    disconnect,
  }
}
