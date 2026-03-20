import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of } from 'rxjs';
import { map, switchMap, catchError, takeUntil } from 'rxjs/operators';
import { DashboardActions } from './dashboard.actions';
import { DashboardApiService } from '../dashboard-api.service';
import { WebSocketService } from '../../../core/websocket.service';
import { IPortfolio, ITrade, ISignal } from '../../../shared/models';

@Injectable()
export class DashboardEffects {
  private readonly actions$ = inject(Actions);
  private readonly dashboardApi = inject(DashboardApiService);
  private readonly ws = inject(WebSocketService);

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

  wsPortfolio$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DashboardActions.startPolling),
      switchMap(() =>
        this.ws.topic$<IPortfolio>('portfolio').pipe(
          takeUntil(this.actions$.pipe(ofType(DashboardActions.stopPolling))),
          map(portfolio => DashboardActions.wsPortfolioUpdate({ portfolio })),
        )
      ),
    )
  );

  wsTrades$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DashboardActions.startPolling),
      switchMap(() =>
        this.ws.topic$<ITrade[]>('trade').pipe(
          takeUntil(this.actions$.pipe(ofType(DashboardActions.stopPolling))),
          map(trades => DashboardActions.wsTradesUpdate({ trades })),
        )
      ),
    )
  );

  wsSignals$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DashboardActions.startPolling),
      switchMap(() =>
        this.ws.topic$<ISignal[]>('signal').pipe(
          takeUntil(this.actions$.pipe(ofType(DashboardActions.stopPolling))),
          map(signals => DashboardActions.wsSignalsUpdate({ signals })),
        )
      ),
    )
  );
}
