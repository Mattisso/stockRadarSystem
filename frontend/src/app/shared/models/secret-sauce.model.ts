export interface ISecretUniverseDaily {
  id: number;
  trade_date: string;
  ticker: string;
  exchange: string;
  open_price: number | null;
  prev_close: number | null;
  last_price: number | null;
  avg_volume: number | null;
  created_at: string;
}

export interface ISecretL1Candidate {
  id: number;
  ticker: string;
  detected_at: string;
  breakout_score: number;
  price: number | null;
  pct_change_1m: number | null;
  pct_change_5m: number | null;
  volume_ratio: number | null;
  reason_flags: string | null;
  created_at: string;
}

export interface ISecretL1ToL2Event {
  id: number;
  ticker: string;
  detect_ts: string;
  escalate_ts: string;
  latency_ms: number | null;
  slot_id: string | null;
  escalation_reason: string | null;
  handoff_payload: string | null;
  created_at: string;
}
