import { Routes } from '@angular/router';
import { provideDashboardState } from './+state/dashboard.providers';

export const DASHBOARD_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./dashboard-page/dashboard-page.component').then(m => m.DashboardPageComponent),
    providers: [provideDashboardState()],
  },
];
