import { provideEffects } from '@ngrx/effects';
import { provideState } from '@ngrx/store';

import { StateMonitorEffects } from './state-monitor.effects';
import { stateMonitorFeature } from './state-monitor.reducer';

export function provideStateMonitorState() {
  return [
    provideState(stateMonitorFeature),
    provideEffects(StateMonitorEffects),
  ];
}
