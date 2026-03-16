import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of, interval, EMPTY } from 'rxjs';
import { map, switchMap, catchError, takeUntil } from 'rxjs/operators';
import { DashboardActions } from './dashboard.actions';
import { DashboardApiService } from '../dashboard-api.service';

@Injectable()
export class DashboardEffects {
  private readonly actions$ = inject(Actions);
  private readonly dashboardApi = inject(DashboardApiService);

  loadDashboard$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DashboardActions.loadDashboard),
      switchMap(() =>
        this.dashboardApi.loadDashboard().pipe(
          map(data => DashboardActions.dashboardLoaded({ data })),
          catchError(error =>
            of(DashboardActions.dashboardLoadFailed({ error: error.message }))
          ),
        )
      ),
    )
  );

  polling$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DashboardActions.startPolling),
      switchMap(() =>
        interval(5000).pipe(
          takeUntil(this.actions$.pipe(ofType(DashboardActions.stopPolling))),
          map(() => DashboardActions.loadDashboard()),
        )
      ),
    )
  );
}
