import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`
const RECONNECT_DELAY = 2000

export function useMarketData() {
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        setData(msg)
      } catch (_) {}
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectRef.current = setTimeout(connect, RECONNECT_DELAY)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const startBot = useCallback(async () => {
    await fetch('/api/bot/start', { method: 'POST' })
  }, [])

  const stopBot = useCallback(async () => {
    await fetch('/api/bot/stop', { method: 'POST' })
  }, [])

  const updateConfig = useCallback(async (config) => {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
  }, [])

  return { data, connected, startBot, stopBot, updateConfig }
}
