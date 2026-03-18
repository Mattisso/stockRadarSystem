import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { ISymbol } from '../../../shared/models';

export const UniverseActions = createActionGroup({
  source: 'Universe',
  events: {
    'Load Symbols': emptyProps(),
    'Symbols Loaded': props<{ symbols: ISymbol[] }>(),
    'Symbols Load Failed': props<{ error: string }>(),
  },
});
