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
  buy_second_bar_ts: string | null;
  buy_price_from_second_market: number | null;
  sell_second_bar_ts: string | null;
  sell_price_from_second_market: number | null;
  second_market_pnl_abs: number | null;
  second_market_pnl_pct: number | null;
  buy_minute_bar_ts: string | null;
  buy_price_from_minute_market: number | null;
  sell_minute_bar_ts: string | null;
  sell_price_from_minute_market: number | null;
  minute_market_pnl_abs: number | null;
  minute_market_pnl_pct: number | null;
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

export interface IDecisionRuntimeKpis {
  generated_at: string;
  window_minutes: number;
  trade_date: string;
  polygon_connected: boolean;
  polygon_subscriptions_paused: boolean;
  polygon_subscription_count: number;
  last_minute_aggregate_event_at: string | null;
  last_second_aggregate_event_at: string | null;
  last_aggregate_persisted_at: string | null;
  last_minute_persisted_at: string | null;
  last_second_persisted_at: string | null;
  aggregate_stream_pending_count: number;
  aggregate_stream_lag_count: number;
  trigger_stream_pending_count: number;
  trigger_stream_lag_count: number;
  persistence_last_flush_completed_at: string | null;
  persistence_last_flush_latency_ms: number | null;
  persistence_last_batch_event_count: number;
  persistence_last_batch_minute_count: number;
  persistence_last_batch_second_count: number;
  persistence_error_count: number;
  persistence_last_error_at: string | null;
  persistence_last_error_message: string | null;
  candidate_events_window_count: number;
  processed_candidate_events_window_count: number;
  unprocessed_candidate_events_window_count: number;
  decision_events_window_count: number;
  candidate_decision_count: number;
  buy_decision_count: number;
  manage_decision_count: number;
  sell_decision_count: number;
  reject_decision_count: number;
  second_stream_stale_reject_count: number;
  minute_stream_stale_reject_count: number;
  second_stale_symbols_count: number;
  minute_stale_symbols_count: number;
  minute_live_row_count: number;
  second_live_row_count: number;
  minute_live_symbol_count: number;
  second_live_symbol_count: number;
  minute_without_second_symbol_count: number;
}
