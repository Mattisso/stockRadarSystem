import { Routes } from '@angular/router';

export const AGGREGATE_DATA_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'live-state',
  },
  {
    path: 'live-state',
    loadComponent: () =>
      import('./aggregate-data-page/aggregate-data-page.component').then(m => m.AggregateDataPageComponent),
    data: { dataset: 'live-state' },
  },
  {
    path: 'candidate-events',
    loadComponent: () =>
      import('./aggregate-data-page/aggregate-data-page.component').then(m => m.AggregateDataPageComponent),
    data: { dataset: 'candidate-events' },
  },
];
