import { createFeature, createReducer, on } from '@ngrx/store';
import { TradesActions } from './trades.actions';
import { initialTradesState, tradesAdapter } from './trades.state';

export const tradesFeature = createFeature({
  name: 'trades',
  reducer: createReducer(
    initialTradesState,

    on(TradesActions.loadTrades, state => ({
      ...state,
      loading: true,
      error: null,
    })),

    on(TradesActions.tradesLoaded, (state, { trades }) =>
      tradesAdapter.setAll(trades, { ...state, loading: false })
    ),

    on(TradesActions.tradesLoadFailed, (state, { error }) => ({
      ...state,
      loading: false,
      error,
    })),
  ),
  extraSelectors: ({ selectTradesState }) => ({
    ...tradesAdapter.getSelectors(selectTradesState),
  }),
});

export const {
  selectAll: selectAllTrades,
  selectTotal: selectTradeCount,
  selectLoading: selectTradesLoading,
  selectError: selectTradesError,
} = tradesFeature;
