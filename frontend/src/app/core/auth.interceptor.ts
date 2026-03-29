import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs/operators';
import { AuthService } from './auth.service';
import { runtimeConfig } from './runtime-config';

function withApiBaseUrl(url: string): string {
  if (!url.startsWith('/api')) {
    return url;
  }

  const suffix = url.slice('/api'.length);
  return `${runtimeConfig.apiBaseUrl}${suffix}`;
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.token;

  const rewrittenReq = req.clone({ url: withApiBaseUrl(req.url) });
  const authReq = token
    ? rewrittenReq.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : rewrittenReq;

  return next(authReq).pipe(
    tap({
      error: (err: HttpErrorResponse) => {
        if (err.status === 401 && !req.url.includes('/auth/token')) {
          auth.logout();
        }
      },
    }),
  );
};
