type Handler = (data: any) => void

export class WsClient {
  private ws: WebSocket | null = null
  private handlers = new Map<string, Handler[]>()

  connect(token: string) {
    const wsUrl = (import.meta as any).env.VITE_WS_URL || (
      window.location.hostname.includes('localhost') || window.location.hostname.includes('127.0.0.1')
        ? `ws://${window.location.hostname}:8000`
        : `wss://classguard-backend.onrender.com`
    )
    this.ws = new WebSocket(`${wsUrl}/ws/faculty?token=${token}`)

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const hs = this.handlers.get(msg.event) || []
        hs.forEach((h) => h(msg.data))
      } catch {}
    }

    this.ws.onclose = () => {
      setTimeout(() => {
        const token = localStorage.getItem('token')
        if (token) this.connect(token)
      }, 3000)
    }
  }

  on(event: string, handler: Handler) {
    if (!this.handlers.has(event)) this.handlers.set(event, [])
    this.handlers.get(event)!.push(handler)
    return () => {
      const hs = this.handlers.get(event)
      if (hs) this.handlers.set(event, hs.filter((h) => h !== handler))
    }
  }

  disconnect() {
    this.ws?.close()
    this.ws = null
  }
}

export const wsClient = new WsClient()
