import { describe, expect, it } from 'vitest';

import { StageBadgePipe } from './stage-badge.pipe';

describe('StageBadgePipe', () => {
  it('formats known state-machine stages', () => {
    const pipe = new StageBadgePipe();

    expect(pipe.transform('normal')).toBe('Normal');
    expect(pipe.transform('watching')).toBe('Watching');
    expect(pipe.transform('candidate')).toBe('Candidate');
    expect(pipe.transform('l2_confirm')).toBe('L2 Confirm');
    expect(pipe.transform('ready_to_buy')).toBe('Ready to Buy');
  });

  it('falls back safely for unknown or null values', () => {
    const pipe = new StageBadgePipe();

    expect(pipe.transform('mystery')).toBe('mystery');
    expect(pipe.transform(null)).toBe('-');
  });
});
