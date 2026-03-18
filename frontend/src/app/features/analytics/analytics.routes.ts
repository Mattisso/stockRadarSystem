import { Routes } from '@angular/router';
import { provideAnalyticsState } from './+state/analytics.providers';

export const ANALYTICS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./analytics-page/analytics-page.component').then(m => m.AnalyticsPageComponent),
    providers: [provideAnalyticsState()],
  },
];
