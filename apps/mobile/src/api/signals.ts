import {apiClient, getDeviceId, BASE_URL} from './client';
import {Signal, ActiveScanner} from '../types';

export const signalsApi = {
  // List signals
  async list(params?: {
    strategy_id?: string;
    pair?: string;
    limit?: number;
  }): Promise<Signal[]> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.get('/signals', {
      params: {device_id: deviceId, ...params},
    });
    return data;
  },

  // Get stats
  async getStats(): Promise<{
    total_signals: number;
    hit_rate: number | null;
    avg_pnl_pct: number | null;
    wins: number;
    losses: number;
  }> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.get(`/signals/stats/${deviceId}`);
    return data;
  },

  // Activate scanner for a strategy
  async activateScanner(
    strategyId: string,
    fcmToken?: string,
  ): Promise<ActiveScanner> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.post('/scanners/activate', {
      strategy_id: strategyId,
      device_id: deviceId,
      fcm_token: fcmToken ?? null,
    });
    return data;
  },

  // Deactivate scanner
  async deactivateScanner(scannerId: string): Promise<void> {
    await apiClient.delete(`/scanners/${scannerId}`);
  },

  // List active scanners
  async listScanners(): Promise<ActiveScanner[]> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.get('/scanners', {
      params: {device_id: deviceId},
    });
    return data;
  },

  // Update FCM token for all scanners
  async updateFcmToken(scannerId: string, fcmToken: string): Promise<void> {
    await apiClient.put(`/scanners/${scannerId}/fcm-token`, null, {
      params: {fcm_token: fcmToken},
    });
  },
};

// WebSocket connection for real-time signals
export function createSignalWebSocket(
  deviceId: string,
  onSignal: (signal: Signal) => void,
  onConnect?: () => void,
): WebSocket {
  const wsUrl = BASE_URL.replace('http', 'ws') + `/api/v1/ws/signals/${deviceId}`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('Signal WebSocket connected');
    onConnect?.();
  };

  ws.onmessage = event => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'signal') {
        onSignal(data.signal);
      } else if (data.type === 'heartbeat' || data.type === 'pong') {
        // keep-alive, ignore
      }
    } catch (e) {
      console.warn('WS parse error:', e);
    }
  };

  ws.onerror = err => console.error('WS error:', err);

  ws.onclose = () => console.log('Signal WebSocket disconnected');

  // Send ping every 20s to keep connection alive
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({type: 'ping'}));
    }
  }, 20000);

  // Cleanup on close
  const originalClose = ws.close.bind(ws);
  ws.close = () => {
    clearInterval(pingInterval);
    originalClose();
  };

  return ws;
}
