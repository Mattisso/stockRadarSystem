export interface IPosition {
  ticker: string;
  quantity: number;
  avg_cost: number;
  market_value: number;
  unrealized_pnl: number;
}

export interface IPortfolio {
  cash_balance: number;
  total_value: number;
  buying_power: number;
  positions: IPosition[];
  daily_pnl: number;
}
