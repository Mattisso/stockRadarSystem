import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { CurrencyPipe, DatePipe, DecimalPipe, UpperCasePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { ITrade } from '../../../shared/models';
import { PnlColorPipe } from '../../../shared/pipes/pnl-color.pipe';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-trades-table',
  standalone: true,
  imports: [CurrencyPipe, DatePipe, DecimalPipe, UpperCasePipe, MatTableModule, PnlColorPipe, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './trades-table.component.html',
  styleUrl: './trades-table.component.scss',
})
export class TradesTableComponent {
  trades = input<ITrade[]>([]);
  displayedColumns = ['ticker', 'side', 'status', 'quantity', 'entry_price', 'exit_price', 'pnl', 'signal_score', 'created_at'];

  statusColor(status: string): 'green' | 'red' | 'orange' | 'grey' {
    switch (status) {
      case 'filled': return 'green';
      case 'cancelled': return 'red';
      case 'pending':
      case 'partial': return 'orange';
      default: return 'grey';
    }
  }
}
