import {apiClient, getDeviceId} from './client';
import {
  Strategy,
  AIStrategyResponse,
  ChatMessage,
} from '../types';

export const strategiesApi = {
  // Generate strategy with AI
  async generateStrategy(
    userInput: string,
    refineStrategyId?: string,
  ): Promise<AIStrategyResponse> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.post('/strategies/generate', {
      user_input: userInput,
      device_id: deviceId,
      refine_strategy_id: refineStrategyId ?? null,
    });
    return data;
  },

  // Chat with AI about strategies
  async chat(messages: ChatMessage[]): Promise<string> {
    const {data} = await apiClient.post('/strategies/chat', messages);
    return data.reply;
  },

  // Save strategy
  async create(
    strategy: Omit<Strategy, 'id' | 'created_at' | 'updated_at' | 'is_active' | 'is_backtested' | 'backtest_score'>,
  ): Promise<Strategy> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.post('/strategies', {
      ...strategy,
      device_id: deviceId,
    });
    return data;
  },

  // List strategies
  async list(filters?: {
    style?: string;
    pair?: string;
    timeframe?: string;
    is_backtested?: boolean;
  }): Promise<Strategy[]> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.get('/strategies', {
      params: {device_id: deviceId, ...filters},
    });
    return data;
  },

  // Get single strategy
  async get(id: string): Promise<Strategy> {
    const {data} = await apiClient.get(`/strategies/${id}`);
    return data;
  },

  // Update strategy
  async update(
    id: string,
    updates: {name?: string; description?: string; definition?: object; change_note?: string},
  ): Promise<Strategy> {
    const {data} = await apiClient.put(`/strategies/${id}`, updates);
    return data;
  },

  // Delete strategy
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/strategies/${id}`);
  },

  // Duplicate strategy
  async duplicate(id: string): Promise<Strategy> {
    const deviceId = await getDeviceId();
    const {data} = await apiClient.post(`/strategies/${id}/duplicate`, null, {
      params: {device_id: deviceId},
    });
    return data;
  },

  // Get versions
  async getVersions(id: string): Promise<any[]> {
    const {data} = await apiClient.get(`/strategies/${id}/versions`);
    return data;
  },
};
