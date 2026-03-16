import { EntityState, EntityAdapter, createEntityAdapter } from '@ngrx/entity';
import { ISymbol } from '../../../shared/models';

export interface UniverseState extends EntityState<ISymbol> {
  loading: boolean;
  error: string | null;
}

export const universeAdapter: EntityAdapter<ISymbol> = createEntityAdapter<ISymbol>({
  selectId: symbol => symbol.id,
  sortComparer: (a, b) => a.ticker.localeCompare(b.ticker),
});

export const initialUniverseState: UniverseState = universeAdapter.getInitialState({
  loading: false,
  error: null,
});
