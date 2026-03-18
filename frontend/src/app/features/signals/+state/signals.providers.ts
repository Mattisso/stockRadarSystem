import { provideState } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { signalsFeature } from './signals.reducer';
import { SignalsEffects } from './signals.effects';

export function provideSignalsState() {
  return [
    provideState(signalsFeature),
    provideEffects(SignalsEffects),
  ];
}
