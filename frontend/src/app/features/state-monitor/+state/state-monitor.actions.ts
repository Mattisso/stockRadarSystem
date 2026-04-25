import { createActionGroup, emptyProps, props } from '@ngrx/store';

import { ISymbolStateLive } from '../../../shared/models/aggregate-data.model';

export const StateMonitorActions = createActionGroup({
  source: 'StateMonitor',
  events: {
    'Load': emptyProps(),
    'Loaded': props<{ entries: ISymbolStateLive[]; summary: Record<string, number> }>(),
    'Load Failed': props<{ error: string }>(),
    'Start Polling': emptyProps(),
    'Stop Polling': emptyProps(),
    'Polling Loaded': props<{ entries: ISymbolStateLive[]; summary: Record<string, number> }>(),
  },
});
