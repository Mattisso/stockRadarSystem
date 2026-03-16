import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { ISignal } from '../../../shared/models';
import { SignalTypePipe } from '../../../shared/pipes/signal-type.pipe';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';

@Component({
  selector: 'app-signal-detail',
  standalone: true,
  imports: [DatePipe, MatCardModule, SignalTypePipe, ScoreBarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './signal-detail.component.html',
  styleUrl: './signal-detail.component.scss',
})
export class SignalDetailComponent {
  signal = input.required<ISignal>();
}
