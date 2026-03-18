import { Routes } from '@angular/router';
import { provideUniverseState } from './+state/universe.providers';

export const UNIVERSE_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./universe-page/universe-page.component').then(m => m.UniversePageComponent),
    providers: [provideUniverseState()],
  },
];
