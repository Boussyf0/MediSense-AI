import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AlertWebSocket } from '@/lib/ws';

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.closed = true;
  }
}

describe('AlertWebSocket', () => {
  let ws: AlertWebSocket;

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    ws = new AlertWebSocket();
  });

  afterEach(() => {
    ws.disconnect();
    vi.unstubAllGlobals();
  });

  it('connect opens a WebSocket with correct URL', () => {
    ws.connect('doctor', 'test-token');
    expect(MockWebSocket.instances.length).toBe(1);
    const instance = MockWebSocket.instances[0];
    expect(instance.url).toContain('/api/v1/ws/alerts/doctor');
    expect(instance.url).toContain('token=test-token');
  });

  it('on handler receives parsed messages', () => {
    const handler = vi.fn();
    ws.on(handler);
    ws.connect('doctor', 'tok');

    const instance = MockWebSocket.instances[0];
    // Simulate incoming message
    instance.onmessage?.({
      data: JSON.stringify({
        type: 'anomaly',
        patient_uuid: 'p-123',
        score_5m: 0.87,
      }),
    });

    expect(handler).toHaveBeenCalledWith({
      type: 'anomaly',
      patient_uuid: 'p-123',
      score_5m: 0.87,
    });
  });

  it('disconnect closes and prevents reconnect', () => {
    ws.connect('doctor', 'tok');
    const instance = MockWebSocket.instances[0];

    ws.disconnect();
    expect(instance.closed).toBe(true);

    // Triggering onclose should NOT create a new WebSocket
    instance.onclose?.();
    expect(MockWebSocket.instances.length).toBe(1);
  });
});
