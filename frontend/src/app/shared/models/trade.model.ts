export type TradeSide = 'buy' | 'sell';
export type TradeStatus = 'pending' | 'filled' | 'partial' | 'cancelled' | 'closed';

export interface ITrade {
  id: number;
  ticker: string;
  side: TradeSide;
  status: TradeStatus;
  quantity: number;
  entry_price: number | null;
  exit_price: number | null;
  stop_loss_price: number | null;
  target_price: number | null;
  pnl: number | null;
  signal_score: number | null;
  entry_time: string | null;
  exit_time: string | null;
  created_at: string;
}
