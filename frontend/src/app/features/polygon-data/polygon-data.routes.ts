import { Routes } from '@angular/router';

export const POLYGON_DATA_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./polygon-data-page/polygon-data-page.component').then(m => m.PolygonDataPageComponent),
  },
];
