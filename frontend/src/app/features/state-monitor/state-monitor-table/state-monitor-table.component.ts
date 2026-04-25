import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatTableModule } from '@angular/material/table';

import { ISymbolStateLive } from '../../../shared/models/aggregate-data.model';
import { TimeAgoPipe } from '../../../shared/pipes/time-ago.pipe';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

export function stateMonitorStatusLabel(status: string): string {
  switch (status) {
    case 'idle': return 'Watching';
    case 'validated': return 'Candidate';
    case 'manage': return 'Manage';
    case 'buy': return 'Buy';
    case 'sold': return 'Sold';
    case 'candidate': return 'Candidate';
    case 'rejected': return 'Rejected';
    default: return status;
  }
}

export function stateMonitorStatusColor(status: string): 'green' | 'red' | 'orange' | 'amber' | 'blue' | 'grey' {
  switch (status) {
    case 'buy': return 'green';
    case 'manage': return 'blue';
    case 'candidate':
    case 'validated':
      return 'orange';
    case 'idle':
      return 'amber';
    case 'sold':
      return 'grey';
    case 'rejected':
      return 'red';
    default:
      return 'grey';
  }
}

@Component({
  selector: 'app-state-monitor-table',
  standalone: true,
  imports: [MatTableModule, TimeAgoPipe, ScoreBarComponent, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './state-monitor-table.component.html',
  styleUrl: './state-monitor-table.component.scss',
})
export class StateMonitorTableComponent {
  entries = input<ISymbolStateLive[]>([]);

  displayedColumns = ['ticker', 'status', 'candidate_score', 'validation_pass_count', 'last_second_ts', 'last_minute_ts', 'streams', 'updated_at'];

  statusLabel(status: string): string {
    return stateMonitorStatusLabel(status);
  }

  statusColor(status: string): 'green' | 'red' | 'orange' | 'amber' | 'blue' | 'grey' {
    return stateMonitorStatusColor(status);
  }
}
