import { ISymbolStateLive } from '../../../shared/models/aggregate-data.model';

export interface StateMonitorState {
  entries: ISymbolStateLive[];
  summary: Record<string, number>;
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
}

export const initialStateMonitorState: StateMonitorState = {
  entries: [],
  summary: {},
  loading: false,
  error: null,
  lastUpdated: null,
};
