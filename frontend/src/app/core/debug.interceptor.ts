import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs/operators';
import { DebugStorageService } from './debug-storage.service';

export const debugInterceptor: HttpInterceptorFn = (req, next) => {
  const debugStorage = inject(DebugStorageService);

  return next(req).pipe(
    tap({
      next: (event) => {
        if (event instanceof HttpResponse) {
          const curl = event.headers.get('X-Curl');
          const tables = event.headers.get('X-Tables');
          const responseTime = event.headers.get('X-Response-Time-Ms');

          if (curl || tables) {
            debugStorage.setLastRequest({
              url: req.url,
              method: req.method,
              curl: curl || '',
              tables: tables ? tables.split(',') : [],
              responseTimeMs: responseTime || '0',
              timestamp: new Date()
            });
          }
        }
      }
    })
  );
};
