import { EntityState, EntityAdapter, createEntityAdapter } from '@ngrx/entity';
import { ISignal } from '../../../shared/models';

export interface SignalsState extends EntityState<ISignal> {
  selectedSignalId: number | null;
  loading: boolean;
  error: string | null;
}

export const signalsAdapter: EntityAdapter<ISignal> = createEntityAdapter<ISignal>({
  selectId: signal => signal.id,
  sortComparer: (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
});

export const initialSignalsState: SignalsState = signalsAdapter.getInitialState({
  selectedSignalId: null,
  loading: false,
  error: null,
});
