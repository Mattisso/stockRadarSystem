export type SignalType = 'breakout' | 'false_breakout';

export type SymbolStage = 'normal' | 'watching' | 'candidate' | 'l2_confirm' | 'ready_to_buy';

export interface ISignal {
  id: number;
  ticker: string;
  signal_type: SignalType;
  score: number;
  liquidity_imbalance: number | null;
  spread_compression: number | null;
  bid_stacking: number | null;
  volume_acceleration: number | null;
  order_aggression: number | null;
  stage: SymbolStage | null;
  reason: string | null;
  ml_confidence: number | null;
  acted_on: boolean;
  outcome_pnl: number | null;
  created_at: string;
}
