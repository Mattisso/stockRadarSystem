import { provideState } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { dashboardFeature } from './dashboard.reducer';
import { DashboardEffects } from './dashboard.effects';

export function provideDashboardState() {
  return [
    provideState(dashboardFeature),
    provideEffects(DashboardEffects),
  ];
}
