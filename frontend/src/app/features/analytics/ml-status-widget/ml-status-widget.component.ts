import { Component, ChangeDetectionStrategy, input, output } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { IMlStatus } from '../../../shared/models';

@Component({
  selector: 'app-ml-status-widget',
  standalone: true,
  imports: [PercentPipe, MatCardModule, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './ml-status-widget.component.html',
  styleUrl: './ml-status-widget.component.scss',
})
export class MlStatusWidgetComponent {
  mlStatus = input<IMlStatus | null>(null);
  retraining = input(false);
  retrain = output<void>();

  get importanceEntries(): [string, number][] {
    const status = this.mlStatus();
    if (!status?.feature_importances) return [];
    return Object.entries(status.feature_importances).sort((a, b) => b[1] - a[1]);
  }

  onRetrain(): void {
    this.retrain.emit();
  }
}
