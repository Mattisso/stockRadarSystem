import { Component, ChangeDetectionStrategy, computed, inject, OnInit, signal } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Store } from '@ngrx/store';
import { TradesActions } from '../+state/trades.actions';
import { selectAllTrades, selectTradesLoading, selectTradesError } from '../+state/trades.reducer';
import { TradesTableComponent } from '../trades-table/trades-table.component';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import { ITrade, TradeSide, TradeStatus } from '../../../shared/models';

@Component({
  selector: 'app-trades-page',
  standalone: true,
  imports: [TradesTableComponent, LoadingComponent, FormsModule, TitleCasePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './trades-page.component.html',
  styleUrl: './trades-page.component.scss',
})
export class TradesPageComponent implements OnInit {
  private readonly store = inject(Store);

  trades = this.store.selectSignal(selectAllTrades);
  loading = this.store.selectSignal(selectTradesLoading);
  error = this.store.selectSignal(selectTradesError);
  tickerFilter = signal('');
  sideFilter = signal<'all' | TradeSide>('all');
  statusFilter = signal<'all' | TradeStatus>('all');
  viewMode = signal<'closed_only' | 'open_and_closed' | 'all'>('closed_only');
  dateFromFilter = signal('');
  dateToFilter = signal('');

  filteredTrades = computed(() =>
    this.trades().filter((trade) => this.matchesFilters(trade))
  );

  readonly sideOptions: Array<'all' | TradeSide> = ['all', 'buy', 'sell'];
  readonly statusOptions: Array<'all' | TradeStatus> = ['all', 'pending', 'filled', 'partial', 'cancelled', 'closed'];
  readonly viewModeOptions: Array<{ value: 'closed_only' | 'open_and_closed' | 'all'; label: string }> = [
    { value: 'closed_only', label: 'Closed only' },
    { value: 'open_and_closed', label: 'Open + Closed' },
    { value: 'all', label: 'All' },
  ];

  ngOnInit(): void {
    this.store.dispatch(TradesActions.loadTrades());
  }

  updateTickerFilter(value: string): void {
    this.tickerFilter.set(value);
  }

  updateSideFilter(value: 'all' | TradeSide): void {
    this.sideFilter.set(value);
  }

  updateStatusFilter(value: 'all' | TradeStatus): void {
    this.statusFilter.set(value);
  }

  updateViewMode(value: 'closed_only' | 'open_and_closed' | 'all'): void {
    this.viewMode.set(value);
  }

  updateDateFromFilter(value: string): void {
    this.dateFromFilter.set(value);
  }

  updateDateToFilter(value: string): void {
    this.dateToFilter.set(value);
  }

  clearFilters(): void {
    this.tickerFilter.set('');
    this.sideFilter.set('all');
    this.statusFilter.set('all');
    this.viewMode.set('closed_only');
    this.dateFromFilter.set('');
    this.dateToFilter.set('');
  }

  private matchesFilters(trade: ITrade): boolean {
    const tickerFilter = this.tickerFilter().trim().toLowerCase();
    if (tickerFilter && !trade.ticker.toLowerCase().includes(tickerFilter)) {
      return false;
    }

    if (this.sideFilter() !== 'all' && trade.side !== this.sideFilter()) {
      return false;
    }

    if (!this.matchesViewMode(trade.status)) {
      return false;
    }

    if (this.statusFilter() !== 'all' && trade.status !== this.statusFilter()) {
      return false;
    }

    const tradeDate = new Date(trade.created_at);
    const dateFrom = this.dateFromFilter();
    if (dateFrom) {
      const from = new Date(`${dateFrom}T00:00:00`);
      if (tradeDate < from) {
        return false;
      }
    }

    const dateTo = this.dateToFilter();
    if (dateTo) {
      const to = new Date(`${dateTo}T23:59:59.999`);
      if (tradeDate > to) {
        return false;
      }
    }

    return true;
  }

  private matchesViewMode(status: TradeStatus): boolean {
    switch (this.viewMode()) {
      case 'closed_only':
        return status === 'closed';
      case 'open_and_closed':
        return status === 'filled' || status === 'closed';
      default:
        return true;
    }
  }
}
