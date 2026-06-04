export type AlertPayload = {
  type: string;
  patient_uuid?: string;
  score_5m?: number | null;
  score_60m?: number | null;
  narrative?: string | null;
  reading?: { hr?: number | null; spo2?: number | null; hrv?: number | null };
  ts?: number;
  [k: string]: unknown;
};

type Handler = (data: AlertPayload) => void;

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

function wsBase(): string {
  const http = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  // NEXT_PUBLIC_API_URL may include the /api/v1 prefix (it does in dev) —
  // strip it so we don't double up when we append /api/v1/ws/alerts/...
  return http.replace(/^http/, 'ws').replace(/\/api\/v1\/?$/, '');
}

export class AlertWebSocket {
  private ws: WebSocket | null = null;
  private handlers: Handler[] = [];
  private intentionalClose = false;
  private role = '';
  private token = '';
  private retry = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect(role: string, token: string) {
    this.role = role;
    this.token = token;
    this.intentionalClose = false;
    this.open();
  }

  private open() {
    if (typeof window === 'undefined') return;
    const url = `${wsBase()}/api/v1/ws/alerts/${this.role}?token=${encodeURIComponent(this.token)}`;
    try {
      this.ws = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws.onopen = () => { this.retry = 0; };
    this.ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as AlertPayload;
        this.handlers.forEach((h) => h(data));
      } catch {
        /* ignore non-JSON frames */
      }
    };
    this.ws.onclose = () => {
      if (!this.intentionalClose) this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect() {
    if (this.intentionalClose) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** this.retry, RECONNECT_MAX_MS);
    this.retry += 1;
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }

  on(handler: Handler) {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter((h) => h !== handler);
    };
  }

  disconnect() {
    this.intentionalClose = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.ws?.close();
    this.ws = null;
  }
}

export const alertWs = new AlertWebSocket();
