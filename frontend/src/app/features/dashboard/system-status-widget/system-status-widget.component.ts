import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-system-status-widget',
  standalone: true,
  imports: [DatePipe, MatCardModule, MatIconModule, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './system-status-widget.component.html',
  styleUrl: './system-status-widget.component.scss',
})
export class SystemStatusWidgetComponent {
  healthy = input(false);
  lastUpdated = input<string | null>(null);
}
