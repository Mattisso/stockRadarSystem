import { Component, ChangeDetectionStrategy, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { ISignal } from '../../../shared/models';
import { SignalTypePipe } from '../../../shared/pipes/signal-type.pipe';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-signals-table',
  standalone: true,
  imports: [DatePipe, MatTableModule, SignalTypePipe, ScoreBarComponent, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './signals-table.component.html',
  styleUrl: './signals-table.component.scss',
})
export class SignalsTableComponent {
  signals = input<ISignal[]>([]);
  signalSelected = output<number>();
  displayedColumns = ['ticker', 'signal_type', 'score', 'acted_on', 'created_at'];
}
