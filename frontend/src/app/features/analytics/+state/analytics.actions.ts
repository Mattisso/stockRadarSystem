import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { AnalyticsData } from '../analytics-api.service';
import { IRetrainResponse } from '../../../shared/models';

export const AnalyticsActions = createActionGroup({
  source: 'Analytics',
  events: {
    'Load Analytics': emptyProps(),
    'Analytics Loaded': props<{ data: AnalyticsData }>(),
    'Analytics Load Failed': props<{ error: string }>(),
    'Retrain Model': emptyProps(),
    'Retrain Complete': props<{ result: IRetrainResponse }>(),
    'Retrain Failed': props<{ error: string }>(),
  },
});
