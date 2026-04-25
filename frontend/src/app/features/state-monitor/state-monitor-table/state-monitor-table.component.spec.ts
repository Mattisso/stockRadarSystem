import { describe, expect, it } from 'vitest';

import {
  stateMonitorStatusColor,
  stateMonitorStatusLabel,
} from './state-monitor-table.component';

describe('StateMonitorTableComponent', () => {
  it('maps backend lifecycle statuses to user-facing labels', () => {
    expect(stateMonitorStatusLabel('idle')).toBe('Watching');
    expect(stateMonitorStatusLabel('candidate')).toBe('Candidate');
    expect(stateMonitorStatusLabel('validated')).toBe('Candidate');
    expect(stateMonitorStatusLabel('buy')).toBe('Buy');
    expect(stateMonitorStatusLabel('manage')).toBe('Manage');
    expect(stateMonitorStatusLabel('sold')).toBe('Sold');
    expect(stateMonitorStatusLabel('rejected')).toBe('Rejected');
  });

  it('maps backend lifecycle statuses to badge colors', () => {
    expect(stateMonitorStatusColor('buy')).toBe('green');
    expect(stateMonitorStatusColor('manage')).toBe('blue');
    expect(stateMonitorStatusColor('candidate')).toBe('orange');
    expect(stateMonitorStatusColor('validated')).toBe('orange');
    expect(stateMonitorStatusColor('idle')).toBe('amber');
    expect(stateMonitorStatusColor('sold')).toBe('grey');
    expect(stateMonitorStatusColor('rejected')).toBe('red');
    expect(stateMonitorStatusColor('unknown')).toBe('grey');
  });
});
