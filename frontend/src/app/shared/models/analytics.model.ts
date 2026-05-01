export interface IKpi {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_pnl: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  sharpe_ratio: number;
  avg_hold_time_minutes: number;
  days: number;
}

export interface IMlStatus {
  model_trained: boolean;
  feature_importances: Record<string, number> | null;
  ml_enabled: boolean;
  ml_confidence_weight: number;
  min_training_samples: number;
}

export interface ISignalAccuracyBucket {
  range: string;
  total: number;
  wins: number;
  win_rate: number;
  average_pnl: number;
  expectancy: number;
}

export interface IRetrainResponse {
  status: 'retrained' | 'insufficient_data' | 'error';
  samples: number | null;
  metrics: Record<string, unknown> | null;
}

export interface IDecisionMarketValidationRow {
  ticker: string;
  reason_code: string;
  buy_id: number | null;
  buy_ts: string | null;
  sell_id: number;
  sell_ts: string;
  match_status: string;
  buy_price_from_event: number | null;
  sell_price_from_event: number | null;
  buy_bar_ts: string | null;
  buy_price_from_market: number | null;
  sell_bar_ts: string | null;
  sell_price_from_market: number | null;
  market_pnl_abs: number | null;
  market_pnl_pct: number | null;
}

export interface IDecisionMarketValidationPage {
  trade_date: string;
  total: number;
  page: number;
  page_size: number;
  summary: Record<string, number>;
  items: IDecisionMarketValidationRow[];
}

export interface IDecisionOutcomeDetail {
  reason_code: string;
  ticker: string;
  trade_n: number;
  buy_ts: string;
  sell_ts: string;
  buy_price: number;
  sell_price: number;
  pnl_abs: number;
  pnl_pct: number;
}
