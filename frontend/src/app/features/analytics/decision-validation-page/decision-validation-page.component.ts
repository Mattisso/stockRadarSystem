import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import { IDecisionMarketValidationRow, IDecisionRuntimeKpis } from '../../../shared/models';
import { AnalyticsApiService } from '../analytics-api.service';

type KpiSeverity = 'ok' | 'warn' | 'bad';

@Component({
  selector: 'app-decision-validation-page',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    FormsModule,
    LoadingComponent,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatPaginatorModule,
    MatTableModule,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './decision-validation-page.component.html',
  styleUrl: './decision-validation-page.component.scss',
})
export class DecisionValidationPageComponent {
  private readonly api = inject(AnalyticsApiService);
  private readonly destroyRef = inject(DestroyRef);

  readonly tradeDate = signal(this.defaultTradeDate());
  readonly ticker = signal('');
  readonly reasonCode = signal('');
  readonly pageIndex = signal(0);
  readonly pageSize = signal(50);
  readonly total = signal(0);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly flatfileError = signal<string | null>(null);
  readonly flatfileDownloading = signal(false);
  readonly summary = signal<Record<string, number>>({});
  readonly rows = signal<IDecisionMarketValidationRow[]>([]);
  readonly runtimeKpis = signal<IDecisionRuntimeKpis | null>(null);

  readonly columns = [
    'ticker',
    'reason_code',
    'match_status',
    'buy_ts',
    'sell_ts',
    'buy_price_from_event',
    'sell_price_from_event',
    'buy_price_from_second_market',
    'sell_price_from_second_market',
    'second_market_pnl_pct',
    'buy_price_from_minute_market',
    'sell_price_from_minute_market',
    'minute_market_pnl_pct',
  ];
  readonly pageSizeOptions = [25, 50, 100];
  readonly matchedCount = computed(() => this.summary()['MATCHED'] ?? 0);
  readonly noPriorBuyCount = computed(() => this.summary()['NO_PRIOR_BUY'] ?? 0);
  readonly buyBarNotFoundCount = computed(() => this.summary()['BUY_BAR_NOT_FOUND'] ?? 0);
  readonly sellBarNotFoundCount = computed(() => this.summary()['SELL_BAR_NOT_FOUND'] ?? 0);

  constructor() {
    this.loadRuntimeKpis();
    this.reload();
  }

  reload(): void {
    this.pageIndex.set(0);
    this.loadRuntimeKpis();
    this.fetchPage(0, this.pageSize());
  }

  onPage(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.fetchPage(event.pageIndex, event.pageSize);
  }

  downloadFlatfile(): void {
    const tradeDate = this.tradeDate().trim();
    if (!tradeDate) {
      this.flatfileError.set('Select a trade date before downloading the flatfile.');
      return;
    }

    this.flatfileDownloading.set(true);
    this.flatfileError.set(null);
    this.api
      .downloadFlatfile(tradeDate)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: blob => {
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement('a');
          anchor.href = url;
          anchor.download = `${tradeDate}.csv.gz`;
          anchor.click();
          URL.revokeObjectURL(url);
          this.flatfileDownloading.set(false);
        },
        error: () => {
          this.flatfileDownloading.set(false);
          this.flatfileError.set('Failed to download Polygon flatfile.');
        },
      });
  }

  private fetchPage(page: number, pageSize: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .loadDecisionMarketValidation(
        this.tradeDate().trim(),
        page,
        pageSize,
        this.ticker().trim(),
        this.reasonCode().trim(),
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: response => {
          this.rows.set(response.items);
          this.summary.set(response.summary ?? {});
          this.total.set(response.total);
          this.loading.set(false);
        },
        error: () => {
          this.rows.set([]);
          this.summary.set({});
          this.total.set(0);
          this.loading.set(false);
          this.error.set('Failed to load market validation rows.');
        },
      });
  }

  private loadRuntimeKpis(): void {
    this.api
      .loadDecisionRuntimeKpis(10)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: response => this.runtimeKpis.set(response),
        error: () => this.runtimeKpis.set(null),
      });
  }

  trackByRow(_: number, row: IDecisionMarketValidationRow): string {
    return `${row.ticker}-${row.sell_id}`;
  }

  kpiSeverity(name: string): KpiSeverity {
    const runtime = this.runtimeKpis();
    if (!runtime) {
      return 'warn';
    }
    switch (name) {
      case 'triggers':
        return runtime.candidate_events_window_count > 0 ? 'ok' : 'warn';
      case 'processed':
        return runtime.unprocessed_candidate_events_window_count === 0 ? 'ok' : 'warn';
      case 'unprocessed':
        if (runtime.unprocessed_candidate_events_window_count === 0) {
          return 'ok';
        }
        if (runtime.unprocessed_candidate_events_window_count <= 10) {
          return 'warn';
        }
        return 'bad';
      case 'decisions':
        return runtime.decision_events_window_count > 0 ? 'ok' : 'warn';
      case 'entries':
        return (runtime.candidate_decision_count + runtime.buy_decision_count + runtime.manage_decision_count) > 0
          ? 'ok'
          : 'warn';
      case 'stale_rejects':
        if (runtime.second_stream_stale_reject_count === 0 && runtime.minute_stream_stale_reject_count === 0) {
          return 'ok';
        }
        if (runtime.minute_stream_stale_reject_count <= 5 && runtime.second_stream_stale_reject_count <= 2) {
          return 'warn';
        }
        return 'bad';
      case 'second_stale':
        if (runtime.second_stale_symbols_count === 0) {
          return 'ok';
        }
        if (runtime.second_stale_symbols_count <= 10) {
          return 'warn';
        }
        return 'bad';
      case 'minute_stale':
        if (runtime.minute_stale_symbols_count === 0) {
          return 'ok';
        }
        if (runtime.minute_stale_symbols_count <= 25) {
          return 'warn';
        }
        return 'bad';
      default:
        return 'warn';
    }
  }

  kpiStatusLabel(name: string): string {
    const severity = this.kpiSeverity(name);
    if (severity === 'ok') {
      return 'Healthy';
    }
    if (severity === 'warn') {
      return 'Watch';
    }
    return 'Blocked';
  }

  private defaultTradeDate(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
}
