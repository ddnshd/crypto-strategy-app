import {apiClient} from './client';
import {OHLCVBar} from '../types';

export const marketApi = {
  async getOHLCV(pair: string, timeframe: string, limit = 100): Promise<OHLCVBar[]> {
    const {data} = await apiClient.get('/market/ohlcv', {
      params: {pair, timeframe, limit},
    });
    return data.data;
  },

  async getPrice(pair: string): Promise<number> {
    const {data} = await apiClient.get(`/market/price/${pair}`);
    return data.price;
  },

  async listPairs(quote = 'USDT'): Promise<string[]> {
    const {data} = await apiClient.get('/market/pairs', {params: {quote}});
    return data.pairs;
  },
};
