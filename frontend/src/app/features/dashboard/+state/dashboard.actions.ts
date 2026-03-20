import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { IPortfolio, ITrade, ISignal } from '../../../shared/models';
import { DashboardData } from '../dashboard-api.service';

export const DashboardActions = createActionGroup({
  source: 'Dashboard',
  events: {
    'Load Dashboard': emptyProps(),
    'Dashboard Loaded': props<{ data: DashboardData }>(),
    'Dashboard Load Failed': props<{ error: string }>(),
    'Start Polling': emptyProps(),
    'Stop Polling': emptyProps(),
    'Ws Portfolio Update': props<{ portfolio: IPortfolio }>(),
    'Ws Trades Update': props<{ trades: ITrade[] }>(),
    'Ws Signals Update': props<{ signals: ISignal[] }>(),
  },
});
