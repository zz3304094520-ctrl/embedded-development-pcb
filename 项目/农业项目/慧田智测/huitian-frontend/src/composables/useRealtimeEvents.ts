import { onBeforeUnmount, shallowRef } from 'vue'
import { wsUrl } from '../api'
import type { RealtimeEvent } from '../types'

type UseRealtimeEventsOptions = {
  onRefreshRequested?: () => void
  onSensorRefreshRequested?: () => void
}

const sensorEvents = new Set(['telemetry.created', 'device.status_changed'])

export function useRealtimeEvents(options: UseRealtimeEventsOptions = {}) {
  const realtimeEvents = shallowRef<RealtimeEvent[]>([])
  const wsConnected = shallowRef(false)

  let socket: WebSocket | null = null
  let refreshTimer: number | null = null
  let sensorRefreshTimer: number | null = null
  let eventSequence = 0

  function scheduleRefresh(): void {
    if (!options.onRefreshRequested) return
    if (refreshTimer !== null) {
      window.clearTimeout(refreshTimer)
    }

    refreshTimer = window.setTimeout(() => {
      options.onRefreshRequested?.()
    }, 500)
  }

  function scheduleSensorRefresh(): void {
    if (!options.onSensorRefreshRequested) return
    if (sensorRefreshTimer !== null) {
      window.clearTimeout(sensorRefreshTimer)
    }

    sensorRefreshTimer = window.setTimeout(() => {
      options.onSensorRefreshRequested?.()
    }, 500)
  }

  function pushEvent(event: Omit<RealtimeEvent, 'id'>): void {
    eventSequence += 1
    realtimeEvents.value = [{ ...event, id: eventSequence }, ...realtimeEvents.value].slice(0, 12)
  }

  function connectWebSocket(): void {
    if (socket) socket.close()

    try {
      socket = new WebSocket(wsUrl)
      socket.onopen = () => {
        wsConnected.value = true
      }
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { event?: string; data?: Record<string, unknown> }
          pushEvent({
            event: payload.event ?? 'unknown',
            data: payload.data ?? {},
            receivedAt: new Date().toISOString(),
          })

          if (payload.event && sensorEvents.has(payload.event)) {
            scheduleSensorRefresh()
          } else if (payload.event && payload.event !== 'system.connected') {
            scheduleRefresh()
          }
        } catch {
          pushEvent({
            event: 'message.unreadable',
            data: { message: '收到一条无法解析的实时消息' },
            receivedAt: new Date().toISOString(),
          })
        }
      }
      socket.onclose = () => {
        wsConnected.value = false
      }
      socket.onerror = () => {
        wsConnected.value = false
      }
    } catch {
      wsConnected.value = false
    }
  }

  function closeWebSocket(): void {
    socket?.close()
    socket = null
    if (refreshTimer !== null) {
      window.clearTimeout(refreshTimer)
      refreshTimer = null
    }
    if (sensorRefreshTimer !== null) {
      window.clearTimeout(sensorRefreshTimer)
      sensorRefreshTimer = null
    }
  }

  onBeforeUnmount(closeWebSocket)

  return {
    realtimeEvents,
    wsConnected,
    connectWebSocket,
    closeWebSocket,
  }
}
