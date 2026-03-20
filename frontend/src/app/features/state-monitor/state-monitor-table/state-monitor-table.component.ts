import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatTableModule } from '@angular/material/table';

import { IStateMachineEntry } from '../../../shared/models/state-machine.model';
import { StageBadgePipe } from '../../../shared/pipes/stage-badge.pipe';
import { TimeAgoPipe } from '../../../shared/pipes/time-ago.pipe';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-state-monitor-table',
  standalone: true,
  imports: [MatTableModule, StageBadgePipe, TimeAgoPipe, ScoreBarComponent, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './state-monitor-table.component.html',
  styleUrl: './state-monitor-table.component.scss',
})
export class StateMonitorTableComponent {
  entries = input<IStateMachineEntry[]>([]);

  displayedColumns = ['ticker', 'stage', 'score', 'consecutive_ticks', 'decay_ticks', 'entered_at', 'reason'];

  stageColor(stage: string): 'green' | 'orange' | 'amber' | 'blue' | 'grey' {
    switch (stage) {
      case 'ready_to_buy': return 'green';
      case 'l2_confirm': return 'blue';
      case 'candidate': return 'orange';
      case 'watching': return 'amber';
      default: return 'grey';
    }
  }
}
