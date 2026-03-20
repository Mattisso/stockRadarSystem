import { createActionGroup, emptyProps, props } from '@ngrx/store';

import { IStateMachineEntry } from '../../../shared/models/state-machine.model';

export const StateMonitorActions = createActionGroup({
  source: 'StateMonitor',
  events: {
    'Load': emptyProps(),
    'Loaded': props<{ entries: IStateMachineEntry[] }>(),
    'Load Failed': props<{ error: string }>(),
    'Start Polling': emptyProps(),
    'Stop Polling': emptyProps(),
    'Ws Received': props<{ entries: IStateMachineEntry[] }>(),
  },
});
