import { provideState } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { tradesFeature } from './trades.reducer';
import { TradesEffects } from './trades.effects';

export function provideTradesState() {
  return [
    provideState(tradesFeature),
    provideEffects(TradesEffects),
  ];
}
