import { Routes } from '@angular/router';
import { provideAnalyticsState } from './+state/analytics.providers';

export const ANALYTICS_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('./analytics-page/analytics-page.component').then(m => m.AnalyticsPageComponent),
    providers: [provideAnalyticsState()],
  },
  {
    path: 'decision-validation',
    loadComponent: () =>
      import('./decision-validation-page/decision-validation-page.component').then(
        m => m.DecisionValidationPageComponent,
      ),
  },
  {
    path: 'decision-sequence-report',
    loadComponent: () =>
      import('./decision-sequence-report-page/decision-sequence-report-page.component').then(
        m => m.DecisionSequenceReportPageComponent,
      ),
  },
];
