import { Component, ChangeDetectionStrategy, input } from '@angular/core';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './status-badge.component.html',
  styleUrl: './status-badge.component.scss',
})
export class StatusBadgeComponent {
  label = input.required<string>();
  color = input<'green' | 'red' | 'orange' | 'grey'>('grey');
}
