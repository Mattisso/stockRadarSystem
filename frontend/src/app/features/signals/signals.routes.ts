import { Routes } from '@angular/router';
import { provideSignalsState } from './+state/signals.providers';

export const SIGNALS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./signals-page/signals-page.component').then(m => m.SignalsPageComponent),
    providers: [provideSignalsState()],
  },
];
