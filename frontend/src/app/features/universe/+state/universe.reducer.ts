import { createFeature, createReducer, on } from '@ngrx/store';
import { UniverseActions } from './universe.actions';
import { initialUniverseState, universeAdapter } from './universe.state';

export const universeFeature = createFeature({
  name: 'universe',
  reducer: createReducer(
    initialUniverseState,

    on(UniverseActions.loadSymbols, state => ({
      ...state,
      loading: true,
      error: null,
    })),

    on(UniverseActions.symbolsLoaded, (state, { symbols }) =>
      universeAdapter.setAll(symbols, { ...state, loading: false })
    ),

    on(UniverseActions.symbolsLoadFailed, (state, { error }) => ({
      ...state,
      loading: false,
      error,
    })),
  ),
  extraSelectors: ({ selectUniverseState }) => ({
    ...universeAdapter.getSelectors(selectUniverseState),
  }),
});

export const {
  selectAll: selectAllSymbols,
  selectTotal: selectSymbolCount,
  selectLoading: selectUniverseLoading,
  selectError: selectUniverseError,
} = universeFeature;
