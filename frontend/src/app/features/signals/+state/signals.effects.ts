import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of } from 'rxjs';
import { map, switchMap, catchError, takeUntil } from 'rxjs/operators';
import { SignalsActions } from './signals.actions';
import { SignalsApiService } from '../signals-api.service';
import { WebSocketService } from '../../../core/websocket.service';
import { ISignal } from '../../../shared/models';

@Injectable()
export class SignalsEffects {
  private readonly actions$ = inject(Actions);
  private readonly signalsApi = inject(SignalsApiService);
  private readonly ws = inject(WebSocketService);

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

  wsSignals$ = createEffect(() =>
    this.actions$.pipe(
      ofType(SignalsActions.startPolling),
      switchMap(() =>
        this.ws.topic$<ISignal[]>('signal').pipe(
          takeUntil(this.actions$.pipe(ofType(SignalsActions.stopPolling))),
          map(signals => SignalsActions.wsSignalsReceived({ signals })),
        )
      ),
    )
  );
}
