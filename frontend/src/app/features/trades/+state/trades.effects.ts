import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of } from 'rxjs';
import { map, switchMap, catchError } from 'rxjs/operators';
import { TradesActions } from './trades.actions';
import { TradesApiService } from '../trades-api.service';

@Injectable()
export class TradesEffects {
  private readonly actions$ = inject(Actions);
  private readonly tradesApi = inject(TradesApiService);

  loadTrades$ = createEffect(() =>
    this.actions$.pipe(
      ofType(TradesActions.loadTrades),
      switchMap(() =>
        this.tradesApi.getAll().pipe(
          map(trades => TradesActions.tradesLoaded({ trades })),
          catchError(error =>
            of(TradesActions.tradesLoadFailed({ error: error.message }))
          ),
        )
      ),
    )
  );
}
