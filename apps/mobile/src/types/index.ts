// Strategy Types
export type TradingStyle = 'scalp' | 'intraday' | 'swing' | 'position';

export interface IndicatorCondition {
  indicator: string;
  params: Record<string, number>;
  operator: '<' | '>' | '<=' | '>=' | '==' | 'cross_above' | 'cross_below';
  value?: number;
  compare_to?: string;
}

export interface ExitConditions {
  take_profit_pct?: number;
  stop_loss_pct?: number;
  trailing_stop_pct?: number;
  max_bars_held?: number;
  exit_conditions?: IndicatorCondition[];
}

export interface StrategyDefinition {
  name: string;
  style: TradingStyle;
  pair: string;
  timeframe: string;
  entry_conditions: IndicatorCondition[];
  exit_conditions: ExitConditions;
  filters?: IndicatorCondition[];
  position_size_pct: number;
  notes?: string;
}

export interface Strategy {
  id: string;
  device_id: string;
  name: string;
  description?: string;
  style: TradingStyle;
  pair: string;
  timeframe: string;
  definition: StrategyDefinition;
  is_active: boolean;
  is_backtested: boolean;
  backtest_score?: number;
  created_at: string;
  updated_at: string;
}

// Backtest Types
export interface TradeLog {
  trade_num: number;
  entry_date: string;
  exit_date: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
  pnl_usd: number;
  is_win: boolean;
  exit_reason: string;
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface BacktestResult {
  id: string;
  strategy_id: string;
  pair: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  total_return: number;
  sharpe_ratio?: number;
  avg_rr?: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  score: number;
  is_qualified: boolean;
  equity_curve: EquityPoint[];
  trade_log: TradeLog[];
  walk_forward?: {
    in_sample: WalkForwardPeriod;
    out_of_sample: WalkForwardPeriod;
    degradation_pct: number;
  };
  created_at: string;
}

export interface WalkForwardPeriod {
  period: string;
  win_rate: number;
  profit_factor: number;
  total_return: number;
  total_trades: number;
}

// Signal Types
export interface Signal {
  id: string;
  strategy_id: string;
  strategy_name?: string;
  device_id: string;
  pair: string;
  direction: 'long' | 'short';
  entry_price: number;
  stop_loss?: number;
  take_profit?: number;
  reason?: string;
  triggered_indicators?: Record<string, number>;
  is_hit?: boolean;
  pnl_pct?: number;
  triggered_at: string;
}

// Scanner Types
export interface ActiveScanner {
  id: string;
  strategy_id: string;
  device_id: string;
  fcm_token?: string;
  is_active: boolean;
  last_checked_at?: string;
  last_signal_at?: string;
  created_at: string;
}

// OHLCV Types
export interface OHLCVBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// AI Chat Types
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AIStrategyResponse {
  strategy: StrategyDefinition;
  explanation: string;
  suggestions: string[];
  warnings: string[];
}
