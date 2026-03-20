import { createFeature, createReducer, createSelector, on } from '@ngrx/store';

import { SymbolStage } from '../../../shared/models/signal.model';
import { StateMonitorActions } from './state-monitor.actions';
import { initialStateMonitorState } from './state-monitor.state';

const stageOrder: Record<string, number> = {
  ready_to_buy: 0,
  l2_confirm: 1,
  candidate: 2,
  watching: 3,
};

export const stateMonitorFeature = createFeature({
  name: 'stateMonitor',
  reducer: createReducer(
    initialStateMonitorState,
    on(StateMonitorActions.load, state => ({ ...state, loading: true, error: null })),
    on(StateMonitorActions.loaded, (state, { entries }) => ({
      ...state,
      entries,
      loading: false,
      lastUpdated: new Date().toISOString(),
    })),
    on(StateMonitorActions.loadFailed, (state, { error }) => ({
      ...state,
      loading: false,
      error,
    })),
    on(StateMonitorActions.wsReceived, (state, { entries }) => ({
      ...state,
      entries,
      lastUpdated: new Date().toISOString(),
    })),
  ),
  extraSelectors: ({ selectEntries }) => ({
    selectEntriesSortedByStage: createSelector(selectEntries, entries =>
      [...entries].sort(
        (a, b) => (stageOrder[a.stage] ?? 99) - (stageOrder[b.stage] ?? 99),
      ),
    ),
    selectStageDistribution: createSelector(selectEntries, entries => {
      const counts: Record<string, number> = {
        watching: 0,
        candidate: 0,
        l2_confirm: 0,
        ready_to_buy: 0,
      };
      entries.forEach(e => {
        if (e.stage in counts) counts[e.stage]++;
      });
      return counts;
    }),
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
