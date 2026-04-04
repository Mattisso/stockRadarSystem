import { Routes } from '@angular/router';

export const SECRET_SAUCE_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./secret-sauce-page/secret-sauce-page.component').then(m => m.SecretSaucePageComponent),
  },
];
