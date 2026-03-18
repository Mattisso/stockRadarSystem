import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of } from 'rxjs';
import { map, switchMap, catchError } from 'rxjs/operators';
import { AnalyticsActions } from './analytics.actions';
import { AnalyticsApiService } from '../analytics-api.service';

@Injectable()
export class AnalyticsEffects {
  private readonly actions$ = inject(Actions);
  private readonly api = inject(AnalyticsApiService);

  loadAnalytics$ = createEffect(() =>
    this.actions$.pipe(
      ofType(AnalyticsActions.loadAnalytics),
      switchMap(() =>
        this.api.loadAnalytics().pipe(
          map(data => AnalyticsActions.analyticsLoaded({ data })),
          catchError(error =>
            of(AnalyticsActions.analyticsLoadFailed({ error: error.message }))
          ),
        )
      ),
    )
  );

  retrain$ = createEffect(() =>
    this.actions$.pipe(
      ofType(AnalyticsActions.retrainModel),
      switchMap(() =>
        this.api.retrain().pipe(
          map(result => AnalyticsActions.retrainComplete({ result })),
          catchError(error =>
            of(AnalyticsActions.retrainFailed({ error: error.message }))
          ),
        )
      ),
    )
  );

  reloadAfterRetrain$ = createEffect(() =>
    this.actions$.pipe(
      ofType(AnalyticsActions.retrainComplete),
      map(() => AnalyticsActions.loadAnalytics()),
    )
  );
}
