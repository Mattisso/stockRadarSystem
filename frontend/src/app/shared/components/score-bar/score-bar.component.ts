import { Component, ChangeDetectionStrategy, input, computed } from '@angular/core';
import { DecimalPipe } from '@angular/common';

@Component({
  selector: 'app-score-bar',
  standalone: true,
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './score-bar.component.html',
  styleUrl: './score-bar.component.scss',
})
export class ScoreBarComponent {
  value = input(0);
  max = input(1);

  widthPct = computed(() => {
    const v = this.value();
    const m = this.max();
    if (!m) return 0;
    return Math.min(100, Math.max(0, (v / m) * 100));
  });
}
