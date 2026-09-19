import {apiClient} from './client';
import {BacktestResult} from '../types';

export const backtestApi = {
  // Start a backtest (async, returns backtest_id)
  async run(params: {
    strategy_id: string;
    pair?: string;
    timeframe?: string;
    start_date?: string;
    end_date?: string;
    initial_capital?: number;
    enable_walk_forward?: boolean;
  }): Promise<{backtest_id: string; status: string; message: string}> {
    const {data} = await apiClient.post('/backtest/run', {
      enable_walk_forward: true,
      initial_capital: 1000,
      ...params,
    });
    return data;
  },

  // Poll for result
  async getResult(backtestId: string): Promise<BacktestResult | null> {
    try {
      const {data} = await apiClient.get(`/backtest/${backtestId}`);
      return data;
    } catch (err: any) {
      if (err.message?.includes('not found')) return null; // still running
      throw err;
    }
  },

  // Poll until done (max 5 minutes)
  async waitForResult(
    backtestId: string,
    onProgress?: (attempt: number) => void,
  ): Promise<BacktestResult> {
    const maxAttempts = 60;
    const interval = 5000; // 5 seconds

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      onProgress?.(attempt);
      await new Promise(r => setTimeout(r, interval));
      const result = await this.getResult(backtestId);
      if (result) return result;
    }
    throw new Error('Backtest timeout — silakan coba lagi');
  },

  // Get all backtests for a strategy
  async listForStrategy(strategyId: string): Promise<BacktestResult[]> {
    const {data} = await apiClient.get(`/backtest/strategy/${strategyId}`);
    return data;
  },
};
