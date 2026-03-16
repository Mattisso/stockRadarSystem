import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { ISignal } from '../../../shared/models';

export const SignalsActions = createActionGroup({
  source: 'Signals',
  events: {
    'Load Signals': emptyProps(),
    'Signals Loaded': props<{ signals: ISignal[] }>(),
    'Signals Load Failed': props<{ error: string }>(),
    'Start Polling': emptyProps(),
    'Stop Polling': emptyProps(),
    'Select Signal': props<{ id: number | null }>(),
  },
});
