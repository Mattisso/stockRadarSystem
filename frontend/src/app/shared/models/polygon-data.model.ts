export interface IPolygonDayAggregate {
  id: number;
  trade_date: string;
  ticker: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
  transactions: number | null;
  source_ts: string | null;
  created_at: string;
}

export interface IPolygonMinuteAggregate {
  id: number;
  ticker: string;
  minute_ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
  transactions: number | null;
  created_at: string;
}

export interface IPolygonTick {
  id: number;
  ticker: string;
  event_type: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  tick_ts: string;
  created_at: string;
}
