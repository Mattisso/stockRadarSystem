import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { IPosition } from '../../../shared/models';
import { PnlColorPipe } from '../../../shared/pipes/pnl-color.pipe';

@Component({
  selector: 'app-positions-widget',
  standalone: true,
  imports: [CurrencyPipe, MatCardModule, MatTableModule, PnlColorPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './positions-widget.component.html',
  styleUrl: './positions-widget.component.scss',
})
export class PositionsWidgetComponent {
  positions = input<IPosition[]>([]);
  displayedColumns = ['ticker', 'quantity', 'avg_cost', 'market_value', 'unrealized_pnl'];
}
