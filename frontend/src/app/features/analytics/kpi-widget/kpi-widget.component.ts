import { Component, ChangeDetectionStrategy, input, computed } from '@angular/core';
import { CurrencyPipe, DecimalPipe, PercentPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { IKpi } from '../../../shared/models';
import { PnlColorPipe } from '../../../shared/pipes/pnl-color.pipe';

@Component({
  selector: 'app-kpi-widget',
  standalone: true,
  imports: [CurrencyPipe, DecimalPipe, PercentPipe, MatCardModule, PnlColorPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './kpi-widget.component.html',
  styleUrl: './kpi-widget.component.scss',
})
export class KpiWidgetComponent {
  kpis = input<IKpi | null>(null);

  subtitle = computed(() => {
    const k = this.kpis();
    return k ? `Last ${k.days} days` : '';
  });
}
