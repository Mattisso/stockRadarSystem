import { provideState } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { analyticsFeature } from './analytics.reducer';
import { AnalyticsEffects } from './analytics.effects';

export function provideAnalyticsState() {
  return [
    provideState(analyticsFeature),
    provideEffects(AnalyticsEffects),
  ];
}
