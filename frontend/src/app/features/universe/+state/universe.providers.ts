import { provideState } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { universeFeature } from './universe.reducer';
import { UniverseEffects } from './universe.effects';

export function provideUniverseState() {
  return [
    provideState(universeFeature),
    provideEffects(UniverseEffects),
  ];
}
