import { createFeature, createReducer, on } from '@ngrx/store';
import { AnalyticsActions } from './analytics.actions';
import { initialAnalyticsState } from './analytics.state';

export const analyticsFeature = createFeature({
  name: 'analytics',
  reducer: createReducer(
    initialAnalyticsState,

    on(AnalyticsActions.loadAnalytics, state => ({
      ...state,
      loading: true,
      error: null,
    })),

    on(AnalyticsActions.analyticsLoaded, (state, { data }) => ({
      ...state,
      kpis: data.kpis,
      mlStatus: data.mlStatus,
      signalAccuracy: data.signalAccuracy,
      loading: false,
      error: null,
    })),

    on(AnalyticsActions.analyticsLoadFailed, (state, { error }) => ({
      ...state,
      loading: false,
      error,
    })),

    on(AnalyticsActions.retrainModel, state => ({
      ...state,
      retraining: true,
    })),

    on(AnalyticsActions.retrainComplete, (state, { result }) => ({
      ...state,
      retraining: false,
      mlStatus: state.mlStatus
        ? { ...state.mlStatus, model_trained: result.status === 'retrained' }
        : state.mlStatus,
    })),

    on(AnalyticsActions.retrainFailed, (state, { error }) => ({
      ...state,
      retraining: false,
      error,
    })),
  ),
});

export const {
  selectKpis,
  selectMlStatus,
  selectSignalAccuracy,
  selectLoading,
  selectRetraining,
  selectError,
} = analyticsFeature;
