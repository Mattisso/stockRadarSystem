import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of } from 'rxjs';
import { map, switchMap, catchError } from 'rxjs/operators';
import { UniverseActions } from './universe.actions';
import { UniverseApiService } from '../universe-api.service';

@Injectable()
export class UniverseEffects {
  private readonly actions$ = inject(Actions);
  private readonly universeApi = inject(UniverseApiService);

  loadSymbols$ = createEffect(() =>
    this.actions$.pipe(
      ofType(UniverseActions.loadSymbols),
      switchMap(() =>
        this.universeApi.getAll().pipe(
          map(symbols => UniverseActions.symbolsLoaded({ symbols })),
          catchError(error =>
            of(UniverseActions.symbolsLoadFailed({ error: error.message }))
          ),
        )
      ),
    )
  );
}
