import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { ITrade } from '../../../shared/models';

export const TradesActions = createActionGroup({
  source: 'Trades',
  events: {
    'Load Trades': emptyProps(),
    'Trades Loaded': props<{ trades: ITrade[] }>(),
    'Trades Load Failed': props<{ error: string }>(),
  },
});
