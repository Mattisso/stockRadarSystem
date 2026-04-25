import { createFeature, createReducer, createSelector, on } from '@ngrx/store';

import { StateMonitorActions } from './state-monitor.actions';
import { initialStateMonitorState } from './state-monitor.state';

const statusOrder: Record<string, number> = {
  buy: 0,
  manage: 1,
  candidate: 2,
  validated: 3,
  idle: 4,
  sold: 5,
  rejected: 6,
};

export const stateMonitorFeature = createFeature({
  name: 'stateMonitor',
  reducer: createReducer(
    initialStateMonitorState,
    on(StateMonitorActions.load, state => ({ ...state, loading: true, error: null })),
    on(StateMonitorActions.loaded, (state, { entries, summary }) => ({
      ...state,
      entries,
      summary,
      loading: false,
      lastUpdated: new Date().toISOString(),
    })),
    on(StateMonitorActions.loadFailed, (state, { error }) => ({
      ...state,
      loading: false,
      error,
    })),
    on(StateMonitorActions.pollingLoaded, (state, { entries, summary }) => ({
      ...state,
      entries,
      summary,
      loading: false,
      lastUpdated: new Date().toISOString(),
    })),
  ),
  extraSelectors: ({ selectEntries, selectSummary }) => ({
    selectEntriesSortedByStage: createSelector(selectEntries, entries =>
      [...entries].sort(
        (a, b) => (statusOrder[a.candidate_status] ?? 99) - (statusOrder[b.candidate_status] ?? 99),
      ),
    ),
    selectStageDistribution: createSelector(selectSummary, summary => ({
      watching: summary['watching'] ?? 0,
      candidate: summary['candidate'] ?? 0,
      buy: summary['buy'] ?? 0,
      manage: summary['manage'] ?? 0,
      sold: summary['sold'] ?? 0,
      rejected: summary['rejected'] ?? 0,
    })),
  }),
});

export const {
  selectEntries,
  selectLoading: selectStateMonitorLoading,
  selectError: selectStateMonitorError,
  selectLastUpdated,
  selectEntriesSortedByStage,
  selectStageDistribution,
} = stateMonitorFeature;
