import { IStateMachineEntry } from '../../../shared/models/state-machine.model';

export interface StateMonitorState {
  entries: IStateMachineEntry[];
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
}

export const initialStateMonitorState: StateMonitorState = {
  entries: [],
  loading: false,
  error: null,
  lastUpdated: null,
};
