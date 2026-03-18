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
}

export interface IRetrainResponse {
  status: 'retrained' | 'insufficient_data' | 'error';
  samples: number | null;
  metrics: Record<string, unknown> | null;
}
