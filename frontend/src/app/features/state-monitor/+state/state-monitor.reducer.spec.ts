import { describe, expect, it } from 'vitest';

import { StateMonitorActions } from './state-monitor.actions';
import {
  selectEntriesSortedByStage,
  selectStageDistribution,
  stateMonitorFeature,
} from './state-monitor.reducer';
import { initialStateMonitorState } from './state-monitor.state';

describe('stateMonitorFeature reducer', () => {
  it('stores aggregate live entries and grouped summary keys on load', () => {
    const entries = [
      { ticker: 'AAA', candidate_status: 'manage' },
      { ticker: 'BBB', candidate_status: 'buy' },
    ] as any;
    const summary = { watching: 4, candidate: 3, buy: 2, manage: 1, sold: 5, rejected: 6 };

    const state = stateMonitorFeature.reducer(
      initialStateMonitorState,
      StateMonitorActions.loaded({ entries, summary }),
    );

    expect(state.entries).toEqual(entries);
    expect(state.summary).toEqual(summary);
    expect(state.loading).toBe(false);
    expect(state.lastUpdated).toBeTruthy();
  });

  it('sorts entries by aggregate lifecycle order', () => {
    const state = {
      ...initialStateMonitorState,
      entries: [
        { ticker: 'DDD', candidate_status: 'idle' },
        { ticker: 'CCC', candidate_status: 'sold' },
        { ticker: 'BBB', candidate_status: 'manage' },
        { ticker: 'AAA', candidate_status: 'buy' },
      ],
    } as any;

    const sorted = selectEntriesSortedByStage.projector(state.entries);
    expect(sorted.map((entry: any) => entry.ticker)).toEqual(['AAA', 'BBB', 'DDD', 'CCC']);
  });

  it('maps grouped lifecycle summary fields for state monitor cards', () => {
    const distribution = selectStageDistribution.projector({
      watching: 10,
      candidate: 7,
      buy: 2,
      manage: 3,
      sold: 5,
      rejected: 4,
    });

    expect(distribution).toEqual({
      watching: 10,
      candidate: 7,
      buy: 2,
      manage: 3,
      sold: 5,
      rejected: 4,
    });
  });
});
