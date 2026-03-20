import { SymbolStage } from './signal.model';

export interface IStateMachineEntry {
  ticker: string;
  stage: SymbolStage;
  score: number;
  entered_at: string;
  consecutive_ticks: number;
  decay_ticks: number;
  reason: string | null;
}
