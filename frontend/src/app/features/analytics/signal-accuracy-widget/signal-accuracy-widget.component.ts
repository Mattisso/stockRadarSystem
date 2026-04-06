import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { CurrencyPipe, PercentPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { ISignalAccuracyBucket } from '../../../shared/models';
import { PnlColorPipe } from '../../../shared/pipes/pnl-color.pipe';

@Component({
  selector: 'app-signal-accuracy-widget',
  standalone: true,
  imports: [CurrencyPipe, PercentPipe, MatCardModule, MatTableModule, PnlColorPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './signal-accuracy-widget.component.html',
  styleUrl: './signal-accuracy-widget.component.scss',
})
export class SignalAccuracyWidgetComponent {
  buckets = input<ISignalAccuracyBucket[]>([]);

  displayedColumns = ['range', 'total', 'wins', 'win_rate', 'average_pnl', 'expectancy'];
}
