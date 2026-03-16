export interface ISymbol {
  id: number;
  ticker: string;
  name: string;
  exchange: string;
  last_price: number | null;
  avg_volume: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
