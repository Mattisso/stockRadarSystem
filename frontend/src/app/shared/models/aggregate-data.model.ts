export interface ISymbolStateLive {
  ticker: string;
  last_second_ts: string | null;
  last_minute_ts: string | null;
  seconds_since_last_trade_bar: number | null;
  minutes_since_last_trade_bar: number | null;
  is_second_stream_stale: boolean;
  is_minute_stream_stale: boolean;
  rolling_second_high: number | null;
  rolling_second_low: number | null;
  rolling_second_volume: number;
  rolling_green_count: number;
  current_minute_high: number | null;
  previous_minute_high: number | null;
  candidate_score: number | null;
  candidate_status: string;
  updated_at: string | null;
}

export interface ICandidateEvent {
  id: number;
  ticker: string;
  event_ts: string;
  trigger_name: string;
  trigger_payload: string | null;
  last_second_ts: string | null;
  last_minute_ts: string | null;
  seconds_since_last_trade_bar: number | null;
  minutes_since_last_trade_bar: number | null;
  is_second_stream_stale: boolean;
  is_minute_stream_stale: boolean;
  created_at: string;
}
