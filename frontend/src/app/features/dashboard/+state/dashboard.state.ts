import { IPortfolio, ITrade, ISignal } from '../../../shared/models';

export interface DashboardState {
  portfolio: IPortfolio | null;
  recentTrades: ITrade[];
  activeSignals: ISignal[];
  healthy: boolean;
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
}

export const initialDashboardState: DashboardState = {
  portfolio: null,
  recentTrades: [],
  activeSignals: [],
  healthy: false,
  loading: false,
  error: null,
  lastUpdated: null,
};
