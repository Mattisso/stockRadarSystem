import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { CurrencyPipe, DecimalPipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { ISymbol } from '../../../shared/models';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-universe-table',
  standalone: true,
  imports: [CurrencyPipe, DecimalPipe, MatTableModule, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './universe-table.component.html',
  styleUrl: './universe-table.component.scss',
})
export class UniverseTableComponent {
  symbols = input<ISymbol[]>([]);
  displayedColumns = ['ticker', 'name', 'exchange', 'last_price', 'avg_volume', 'is_active'];
}
