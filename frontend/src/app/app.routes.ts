import { Routes } from '@angular/router';
import { LayoutShellComponent } from './layout/layout-shell/layout-shell.component';

export const routes: Routes = [
  {
    path: '',
    component: LayoutShellComponent,
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadChildren: () =>
          import('./features/dashboard/dashboard.routes').then(m => m.DASHBOARD_ROUTES),
      },
      {
        path: 'universe',
        loadChildren: () =>
          import('./features/universe/universe.routes').then(m => m.UNIVERSE_ROUTES),
      },
      {
        path: 'trades',
        loadChildren: () =>
          import('./features/trades/trades.routes').then(m => m.TRADES_ROUTES),
      },
      {
        path: 'signals',
        loadChildren: () =>
          import('./features/signals/signals.routes').then(m => m.SIGNALS_ROUTES),
      },
      {
        path: 'analytics',
        loadChildren: () =>
          import('./features/analytics/analytics.routes').then(m => m.ANALYTICS_ROUTES),
      },
      {
        path: 'settings',
        loadChildren: () =>
          import('./features/settings/settings.routes').then(m => m.SETTINGS_ROUTES),
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
