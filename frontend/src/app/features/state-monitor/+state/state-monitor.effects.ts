import { inject, Injectable } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { catchError, map, of, switchMap, takeUntil } from 'rxjs';

import { WebSocketService } from '../../../core/websocket.service';
import { IStateMachineEntry } from '../../../shared/models/state-machine.model';
import { StateMonitorApiService } from '../state-monitor-api.service';
import { StateMonitorActions } from './state-monitor.actions';

@Injectable()
export class StateMonitorEffects {
  private readonly actions$ = inject(Actions);
  private readonly api = inject(StateMonitorApiService);
  private readonly ws = inject(WebSocketService);

  load$ = createEffect(() =>
    this.actions$.pipe(
      ofType(StateMonitorActions.load),
      switchMap(() =>
        this.api.getAll().pipe(
          map(entries => StateMonitorActions.loaded({ entries })),
          catchError(error =>
            of(StateMonitorActions.loadFailed({ error: error.message })),
          ),
        ),
      ),
    ),
  );

  wsStream$ = createEffect(() =>
    this.actions$.pipe(
      ofType(StateMonitorActions.startPolling),
      switchMap(() =>
        this.ws.topic$<IStateMachineEntry[]>('state_machine').pipe(
          takeUntil(this.actions$.pipe(ofType(StateMonitorActions.stopPolling))),
          map(entries => StateMonitorActions.wsReceived({ entries })),
        ),
      ),
    ),
  );
}
