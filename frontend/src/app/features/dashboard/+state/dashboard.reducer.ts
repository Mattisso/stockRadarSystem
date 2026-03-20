import { createFeature, createReducer, on } from '@ngrx/store';
import { DashboardActions } from './dashboard.actions';
import { initialDashboardState } from './dashboard.state';

export const dashboardFeature = createFeature({
  name: 'dashboard',
  reducer: createReducer(
    initialDashboardState,

    on(DashboardActions.loadDashboard, state => ({
      ...state,
      loading: true,
      error: null,
    })),

    on(DashboardActions.dashboardLoaded, (state, { data }) => ({
      ...state,
      portfolio: data.portfolio,
      recentTrades: data.recentTrades,
      activeSignals: data.activeSignals,
      healthy: data.health.status === 'ok',
      loading: false,
      error: null,
      lastUpdated: new Date().toISOString(),
    })),

    on(DashboardActions.dashboardLoadFailed, (state, { error }) => ({
      ...state,
      loading: false,
      error,
    })),

    on(DashboardActions.wsPortfolioUpdate, (state, { portfolio }) => ({
      ...state,
      portfolio,
      lastUpdated: new Date().toISOString(),
    })),

    on(DashboardActions.wsTradesUpdate, (state, { trades }) => ({
      ...state,
      recentTrades: trades.slice(0, 5),
      lastUpdated: new Date().toISOString(),
    })),

    on(DashboardActions.wsSignalsUpdate, (state, { signals }) => ({
      ...state,
      activeSignals: signals.slice(0, 10),
      lastUpdated: new Date().toISOString(),
    })),
  ),
});

export const {
  selectPortfolio,
  selectRecentTrades,
  selectActiveSignals,
  selectHealthy,
  selectLoading,
  selectError,
  selectLastUpdated,
} = dashboardFeature;
