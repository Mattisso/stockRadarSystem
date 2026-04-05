export interface IL2SubscriptionStatus {
  ticker: string;
  confirmed: boolean;
  has_depth: boolean;
  bid_levels: number;
  ask_levels: number;
  last_updated_at: number | null;
}

export interface IL2Health {
  active_count: number;
  books_with_depth_count: number;
  subscribed_tickers: string[];
  subscriptions: IL2SubscriptionStatus[];
}
