import { Routes } from '@angular/router';

export const POLYGON_DATA_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'day',
  },
  {
    path: 'day',
    loadComponent: () =>
      import('./polygon-data-page/polygon-data-page.component').then(m => m.PolygonDataPageComponent),
    data: { dataset: 'day' },
  },
  {
    path: 'minute',
    loadComponent: () =>
      import('./polygon-data-page/polygon-data-page.component').then(m => m.PolygonDataPageComponent),
    data: { dataset: 'minute' },
  },
  {
    path: 'second',
    loadComponent: () =>
      import('./polygon-data-page/polygon-data-page.component').then(m => m.PolygonDataPageComponent),
    data: { dataset: 'second' },
  },
  {
    path: 'ticks',
    loadComponent: () =>
      import('./polygon-data-page/polygon-data-page.component').then(m => m.PolygonDataPageComponent),
    data: { dataset: 'ticks' },
  },
];
