import {create} from 'zustand';
import {Strategy, Signal, ActiveScanner, BacktestResult} from '../types';
import {strategiesApi} from '../api/strategies';
import {signalsApi} from '../api/signals';

interface AppState {
  // Strategies
  strategies: Strategy[];
  strategiesLoading: boolean;
  loadStrategies: () => Promise<void>;
  addStrategy: (strategy: Strategy) => void;
  updateStrategy: (strategy: Strategy) => void;
  removeStrategy: (id: string) => void;

  // Signals
  signals: Signal[];
  signalsLoading: boolean;
  loadSignals: () => Promise<void>;
  addSignal: (signal: Signal) => void;

  // Scanners
  scanners: ActiveScanner[];
  loadScanners: () => Promise<void>;
  addScanner: (scanner: ActiveScanner) => void;
  removeScanner: (id: string) => void;

  // Backtest
  backtestResults: Record<string, BacktestResult>; // keyed by backtest_id
  addBacktestResult: (result: BacktestResult) => void;

  // UI
  selectedStrategyId: string | null;
  setSelectedStrategy: (id: string | null) => void;
}

export const useStore = create<AppState>((set, get) => ({
  // Strategies
  strategies: [],
  strategiesLoading: false,
  async loadStrategies() {
    set({strategiesLoading: true});
    try {
      const data = await strategiesApi.list();
      set({strategies: data});
    } catch (e) {
      console.error('loadStrategies error:', e);
    } finally {
      set({strategiesLoading: false});
    }
  },
  addStrategy: strategy =>
    set(state => ({strategies: [strategy, ...state.strategies]})),
  updateStrategy: strategy =>
    set(state => ({
      strategies: state.strategies.map(s => (s.id === strategy.id ? strategy : s)),
    })),
  removeStrategy: id =>
    set(state => ({strategies: state.strategies.filter(s => s.id !== id)})),

  // Signals
  signals: [],
  signalsLoading: false,
  async loadSignals() {
    set({signalsLoading: true});
    try {
      const data = await signalsApi.list({limit: 100});
      set({signals: data});
    } catch (e) {
      console.error('loadSignals error:', e);
    } finally {
      set({signalsLoading: false});
    }
  },
  addSignal: signal =>
    set(state => ({signals: [signal, ...state.signals]})),

  // Scanners
  scanners: [],
  async loadScanners() {
    try {
      const data = await signalsApi.listScanners();
      set({scanners: data});
    } catch (e) {
      console.error('loadScanners error:', e);
    }
  },
  addScanner: scanner =>
    set(state => ({scanners: [scanner, ...state.scanners]})),
  removeScanner: id =>
    set(state => ({scanners: state.scanners.filter(s => s.id !== id)})),

  // Backtest
  backtestResults: {},
  addBacktestResult: result =>
    set(state => ({
      backtestResults: {...state.backtestResults, [result.id]: result},
    })),

  // UI
  selectedStrategyId: null,
  setSelectedStrategy: id => set({selectedStrategyId: id}),
}));
