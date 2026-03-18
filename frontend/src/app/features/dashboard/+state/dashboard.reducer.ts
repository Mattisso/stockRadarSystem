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
