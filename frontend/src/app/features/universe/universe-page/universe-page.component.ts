import { Component, ChangeDetectionStrategy, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Store } from '@ngrx/store';
import { UniverseActions } from '../+state/universe.actions';
import { selectAllSymbols, selectUniverseLoading, selectUniverseError } from '../+state/universe.reducer';
import { UniverseTableComponent } from '../universe-table/universe-table.component';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import { ISymbol } from '../../../shared/models';

@Component({
  selector: 'app-universe-page',
  standalone: true,
  imports: [UniverseTableComponent, LoadingComponent, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './universe-page.component.html',
  styleUrl: './universe-page.component.scss',
})
export class UniversePageComponent implements OnInit {
  private readonly store = inject(Store);

  symbols = this.store.selectSignal(selectAllSymbols);
  loading = this.store.selectSignal(selectUniverseLoading);
  error = this.store.selectSignal(selectUniverseError);
  tickerFilter = signal('');
  exchangeFilter = signal('all');
  statusFilter = signal<'all' | 'active' | 'inactive'>('all');
  pageSize = signal(25);
  currentPage = signal(1);

  filteredSymbols = computed(() =>
    this.symbols().filter((symbol) => this.matchesFilters(symbol))
  );

  totalPages = computed(() => {
    const total = this.filteredSymbols().length;
    return Math.max(1, Math.ceil(total / this.pageSize()));
  });

  pagedSymbols = computed(() => {
    const page = Math.min(this.currentPage(), this.totalPages());
    const start = (page - 1) * this.pageSize();
    return this.filteredSymbols().slice(start, start + this.pageSize());
  });

  exchangeOptions = computed(() => {
    const exchanges = new Set(
      this.symbols()
        .map((symbol) => (symbol.exchange || '').trim())
        .filter((exchange) => exchange.length > 0)
    );
    return ['all', ...Array.from(exchanges).sort((a, b) => a.localeCompare(b))];
  });

  readonly pageSizeOptions = [25, 50, 100];

  ngOnInit(): void {
    this.store.dispatch(UniverseActions.loadSymbols());
  }

  updateTickerFilter(value: string): void {
    this.tickerFilter.set(value);
    this.currentPage.set(1);
  }

  updateExchangeFilter(value: string): void {
    this.exchangeFilter.set(value);
    this.currentPage.set(1);
  }

  updateStatusFilter(value: 'all' | 'active' | 'inactive'): void {
    this.statusFilter.set(value);
    this.currentPage.set(1);
  }

  updatePageSize(value: number | string): void {
    this.pageSize.set(Number(value));
    this.currentPage.set(1);
  }

  previousPage(): void {
    if (this.currentPage() > 1) {
      this.currentPage.set(this.currentPage() - 1);
    }
  }

  nextPage(): void {
    if (this.currentPage() < this.totalPages()) {
      this.currentPage.set(this.currentPage() + 1);
    }
  }

  clearFilters(): void {
    this.tickerFilter.set('');
    this.exchangeFilter.set('all');
    this.statusFilter.set('all');
    this.pageSize.set(25);
    this.currentPage.set(1);
  }

  private matchesFilters(symbol: ISymbol): boolean {
    const tickerFilter = this.tickerFilter().trim().toLowerCase();
    if (tickerFilter && !symbol.ticker.toLowerCase().includes(tickerFilter)) {
      return false;
    }

    const exchangeFilter = this.exchangeFilter();
    if (exchangeFilter !== 'all' && symbol.exchange !== exchangeFilter) {
      return false;
    }

    const statusFilter = this.statusFilter();
    if (statusFilter === 'active' && !symbol.is_active) {
      return false;
    }
    if (statusFilter === 'inactive' && symbol.is_active) {
      return false;
    }

    return true;
  }
}
