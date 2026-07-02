const TOKEN_KEY = 'access_token'

export function connectDatasetProgress(datasetId, { onMessage, onError } = {}) {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token || !datasetId) return () => {}

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  const url = `${proto}://${host}/api/v1/ws/datasets/${datasetId}?token=${encodeURIComponent(token)}`
  let ws
  try {
    ws = new WebSocket(url)
  } catch (e) {
    onError?.(e)
    return () => {}
  }

  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data)
      onMessage?.(data)
    } catch {
      /* ignore */
    }
  }
  ws.onerror = (e) => onError?.(e)

  return () => {
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
  }
}
