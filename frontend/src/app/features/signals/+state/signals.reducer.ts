import { createFeature, createReducer, createSelector, on } from '@ngrx/store';
import { SignalsActions } from './signals.actions';
import { initialSignalsState, signalsAdapter } from './signals.state';

export const signalsFeature = createFeature({
  name: 'signals',
  reducer: createReducer(
    initialSignalsState,

    on(SignalsActions.loadSignals, state => ({
      ...state,
      loading: true,
      error: null,
    })),

    on(SignalsActions.signalsLoaded, (state, { signals }) =>
      signalsAdapter.setAll(signals, { ...state, loading: false })
    ),

    on(SignalsActions.signalsLoadFailed, (state, { error }) => ({
      ...state,
      loading: false,
      error,
    })),

    on(SignalsActions.selectSignal, (state, { id }) => ({
      ...state,
      selectedSignalId: id,
    })),
  ),
  extraSelectors: ({ selectSignalsState, selectSelectedSignalId }) => {
    const adapterSelectors = signalsAdapter.getSelectors(selectSignalsState);
    return {
      ...adapterSelectors,
      selectSelectedSignal: createSelector(
        adapterSelectors.selectEntities,
        selectSelectedSignalId,
        (entities, id) => (id !== null ? entities[id] ?? null : null),
      ),
    };
  },
});

export const {
  selectAll: selectAllSignals,
  selectTotal: selectSignalCount,
  selectLoading: selectSignalsLoading,
  selectError: selectSignalsError,
  selectSelectedSignalId,
  selectSelectedSignal,
} = signalsFeature;
