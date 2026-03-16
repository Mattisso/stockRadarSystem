import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { ISignal } from '../../../shared/models';
import { SignalTypePipe } from '../../../shared/pipes/signal-type.pipe';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';

@Component({
  selector: 'app-active-signals-widget',
  standalone: true,
  imports: [DatePipe, MatCardModule, MatListModule, MatIconModule, SignalTypePipe, ScoreBarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './active-signals-widget.component.html',
  styleUrl: './active-signals-widget.component.scss',
})
export class ActiveSignalsWidgetComponent {
  signals = input<ISignal[]>([]);
}
