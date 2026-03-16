import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { DashboardData } from '../dashboard-api.service';

export const DashboardActions = createActionGroup({
  source: 'Dashboard',
  events: {
    'Load Dashboard': emptyProps(),
    'Dashboard Loaded': props<{ data: DashboardData }>(),
    'Dashboard Load Failed': props<{ error: string }>(),
    'Start Polling': emptyProps(),
    'Stop Polling': emptyProps(),
  },
});
