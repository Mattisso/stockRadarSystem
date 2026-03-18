import { Routes } from '@angular/router';
import { provideTradesState } from './+state/trades.providers';

export const TRADES_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./trades-page/trades-page.component').then(m => m.TradesPageComponent),
    providers: [provideTradesState()],
  },
];
