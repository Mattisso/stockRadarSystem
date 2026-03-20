import { Routes } from '@angular/router';

import { provideStateMonitorState } from './+state/state-monitor.providers';

export const STATE_MONITOR_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./state-monitor-page/state-monitor-page.component').then(
        m => m.StateMonitorPageComponent,
      ),
    providers: [provideStateMonitorState()],
  },
];
