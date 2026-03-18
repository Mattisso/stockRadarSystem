import { EntityState, EntityAdapter, createEntityAdapter } from '@ngrx/entity';
import { ITrade } from '../../../shared/models';

export interface TradesState extends EntityState<ITrade> {
  loading: boolean;
  error: string | null;
}

export const tradesAdapter: EntityAdapter<ITrade> = createEntityAdapter<ITrade>({
  selectId: trade => trade.id,
  sortComparer: (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
});

export const initialTradesState: TradesState = tradesAdapter.getInitialState({
  loading: false,
  error: null,
});
