import { inject, Injectable } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { catchError, interval, map, of, startWith, switchMap, takeUntil } from 'rxjs';

import { StateMonitorApiService } from '../state-monitor-api.service';
import { StateMonitorActions } from './state-monitor.actions';

@Injectable()
export class StateMonitorEffects {
  private readonly actions$ = inject(Actions);
  private readonly api = inject(StateMonitorApiService);

  load$ = createEffect(() =>
    this.actions$.pipe(
      ofType(StateMonitorActions.load),
      switchMap(() =>
        this.api.getAll().pipe(
          map(response => StateMonitorActions.loaded({ entries: response.items, summary: response.summary })),
          catchError(error =>
            of(StateMonitorActions.loadFailed({ error: error.message })),
          ),
        ),
      ),
    ),
  );

  polling$ = createEffect(() =>
    this.actions$.pipe(
      ofType(StateMonitorActions.startPolling),
      switchMap(() =>
        interval(5000).pipe(
          startWith(0),
          takeUntil(this.actions$.pipe(ofType(StateMonitorActions.stopPolling))),
          switchMap(() =>
            this.api.getAll().pipe(
              map(response => StateMonitorActions.pollingLoaded({ entries: response.items, summary: response.summary })),
              catchError(error => of(StateMonitorActions.loadFailed({ error: error.message }))),
            ),
          ),
        ),
      ),
    ),
  );
}
