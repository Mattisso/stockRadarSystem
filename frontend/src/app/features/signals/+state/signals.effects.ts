import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of, interval } from 'rxjs';
import { map, switchMap, catchError, takeUntil } from 'rxjs/operators';
import { SignalsActions } from './signals.actions';
import { SignalsApiService } from '../signals-api.service';

@Injectable()
export class SignalsEffects {
  private readonly actions$ = inject(Actions);
  private readonly signalsApi = inject(SignalsApiService);

  loadSignals$ = createEffect(() =>
    this.actions$.pipe(
      ofType(SignalsActions.loadSignals),
      switchMap(() =>
        this.signalsApi.getAll().pipe(
          map(signals => SignalsActions.signalsLoaded({ signals })),
          catchError(error =>
            of(SignalsActions.signalsLoadFailed({ error: error.message }))
          ),
        )
      ),
    )
  );

  polling$ = createEffect(() =>
    this.actions$.pipe(
      ofType(SignalsActions.startPolling),
      switchMap(() =>
        interval(10000).pipe(
          takeUntil(this.actions$.pipe(ofType(SignalsActions.stopPolling))),
          map(() => SignalsActions.loadSignals()),
        )
      ),
    )
  );
}
