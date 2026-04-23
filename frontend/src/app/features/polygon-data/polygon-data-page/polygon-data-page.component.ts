import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, RouterLink, RouterLinkActive } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatTableModule } from '@angular/material/table';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import {
  IPolygonDayAggregate,
  IPolygonMinuteAggregate,
  IPolygonSecondAggregate,
  IPolygonTick,
} from '../../../shared/models';
import { PolygonDataApiService } from '../polygon-data-api.service';

type PolygonDatasetKey = 'day' | 'minute' | 'second' | 'ticks';

@Component({
  selector: 'app-polygon-data-page',
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
    RouterLinkActive,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './polygon-data-page.component.html',
  styleUrl: './polygon-data-page.component.scss',
})
export class PolygonDataPageComponent implements OnInit {
  private readonly api = inject(PolygonDataApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  readonly dataset = signal<PolygonDatasetKey>('day');
  readonly ticker = signal('');
  readonly tradeDate = signal('');
  readonly sessionTimeEt = signal('04:00');
  readonly pageIndex = signal(0);
  readonly pageSize = signal(25);
  readonly total = signal(0);
  readonly resolvedTradeDate = signal<string | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly tickCursor = signal<string | null>(null);
  readonly nextTickCursor = signal<string | null>(null);
  readonly tickCursorHistory = signal<(string | null)[]>([]);
  readonly tickHasMore = signal(false);
  readonly dayAggregates = signal<IPolygonDayAggregate[]>([]);
  readonly minuteAggregates = signal<IPolygonMinuteAggregate[]>([]);
  readonly secondAggregates = signal<IPolygonSecondAggregate[]>([]);
  readonly ticks = signal<IPolygonTick[]>([]);

  readonly pageSizeOptions = [10, 25, 50, 100];
  readonly dayColumns = ['trade_date', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly minuteColumns = ['minute_ts', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly secondColumns = ['second_ts', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly tickColumns = ['tick_ts', 'ticker', 'event_type', 'bid', 'ask', 'last', 'volume'];
  readonly requestTicker = computed(() => this.ticker().trim().toUpperCase());
  readonly requestTradeDate = computed(() => this.tradeDate().trim() || null);
  readonly showSessionStartFilter = computed(() => this.dataset() === 'minute' || this.dataset() === 'second');
  readonly displayedRowCount = computed(() => {
    switch (this.dataset()) {
      case 'minute':
        return this.minuteAggregates().length;
      case 'second':
        return this.secondAggregates().length;
      case 'ticks':
        return this.ticks().length;
      default:
        return this.dayAggregates().length;
    }
  });
  readonly title = computed(() => {
    switch (this.dataset()) {
      case 'minute':
        return 'Polygon Minute Aggregates';
      case 'second':
        return 'Polygon Second Aggregates';
      case 'ticks':
        return 'Polygon Live Ticks';
      default:
        return 'Polygon Day Aggregates';
    }
  });
  readonly description = computed(() => {
    switch (this.dataset()) {
      case 'minute':
        return 'Recent operational minute bars for the current under-$10 universe. One page at a time, server-side paged.';
      case 'second':
        return 'Recent operational second bars derived from live ticks. Use a ticker filter for the fastest view.';
      case 'ticks':
        return 'Raw persisted live Polygon ticks for the current under-$10 universe. Use a ticker filter for the fastest view.';
      default:
        return 'Daily Polygon bars for the active under-$10 universe.';
    }
  });
  readonly infoMessage = computed(() => {
    if (this.showSessionStartFilter()) {
      return `Showing rows at ${this.sessionTimeEt()} ET. For second bars, this includes all seconds inside that minute.`;
    }
    if (this.dataset() === 'second' && !this.requestTicker()) {
      return 'Default second-aggregate view is limited to a recent operational window to keep the page responsive.';
    }
    if (this.dataset() === 'ticks' && !this.requestTicker()) {
      return 'Raw ticks default to the latest cross-universe page. Add a ticker filter for a narrower view.';
    }
    return null;
  });

  ngOnInit(): void {
    this.route.data.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(data => {
      const routeDataset = data['dataset'];
      this.dataset.set(this.isDataset(routeDataset) ? routeDataset : 'day');
      this.reload();
    });
  }

  reload(): void {
    this.pageIndex.set(0);
    this.tickCursor.set(null);
    this.nextTickCursor.set(null);
    this.tickCursorHistory.set([]);
    this.tickHasMore.set(false);
    this.fetchPage(0, this.pageSize());
  }

  onPage(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.fetchPage(event.pageIndex, event.pageSize);
  }

  private fetchPage(page: number, pageSize: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.clearData();
    const ticker = this.requestTicker();
    const tradeDate = this.requestTradeDate();

    switch (this.dataset()) {
      case 'minute':
        this.api.loadMinuteAggregates(page, pageSize, ticker, tradeDate, this.sessionTimeEt()).subscribe({
          next: response => this.applyResponse('minute', response.items, response.total, response.trade_date),
          error: () => this.handleError('Failed to load Polygon minute aggregates.'),
        });
        break;
      case 'second':
        this.api.loadSecondAggregates(page, pageSize, ticker, tradeDate, this.sessionTimeEt()).subscribe({
          next: response => this.applyResponse('second', response.items, response.total, response.trade_date),
          error: () => this.handleError('Polygon second aggregates are timing out. Narrow the query with a ticker or try again shortly.'),
        });
        break;
      case 'ticks':
        this.api.loadTicks(page, pageSize, ticker, tradeDate, this.tickCursor()).subscribe({
          next: response => this.applyResponse('ticks', response.items, response.total, response.trade_date, response.next_cursor, response.has_more),
          error: () => this.handleError('Failed to load Polygon live ticks.'),
        });
        break;
      default:
        this.api.loadDayAggregates(page, pageSize, ticker, tradeDate).subscribe({
          next: response => this.applyResponse('day', response.items, response.total, response.trade_date),
          error: () => this.handleError('Failed to load Polygon day aggregates.'),
        });
        break;
    }
  }

  private applyResponse(
    dataset: PolygonDatasetKey,
    items: IPolygonDayAggregate[] | IPolygonMinuteAggregate[] | IPolygonSecondAggregate[] | IPolygonTick[],
    total: number | null,
    tradeDate: string | null,
    nextCursor?: string | null,
    hasMore?: boolean,
  ): void {
    this.total.set(total ?? 0);
    this.resolvedTradeDate.set(tradeDate);
    switch (dataset) {
      case 'minute':
        this.minuteAggregates.set(items as IPolygonMinuteAggregate[]);
        break;
      case 'second':
        this.secondAggregates.set(items as IPolygonSecondAggregate[]);
        break;
      case 'ticks':
        this.ticks.set(items as IPolygonTick[]);
        this.nextTickCursor.set(nextCursor ?? null);
        this.tickHasMore.set(hasMore ?? false);
        break;
      default:
        this.dayAggregates.set(items as IPolygonDayAggregate[]);
        break;
    }
    this.loading.set(false);
  }

  private handleError(message: string): void {
    this.error.set(message);
    this.total.set(0);
    this.loading.set(false);
  }

  private clearData(): void {
    this.dayAggregates.set([]);
    this.minuteAggregates.set([]);
    this.secondAggregates.set([]);
    this.ticks.set([]);
  }

  onTickNext(): void {
    const nextCursor = this.nextTickCursor();
    if (!nextCursor || !this.tickHasMore()) {
      return;
    }
    this.tickCursorHistory.set([...this.tickCursorHistory(), this.tickCursor()]);
    this.tickCursor.set(nextCursor);
    const nextPage = this.pageIndex() + 1;
    this.pageIndex.set(nextPage);
    this.fetchPage(nextPage, this.pageSize());
  }

  onTickPrevious(): void {
    const history = this.tickCursorHistory();
    if (!history.length) {
      return;
    }
    const previousCursor = history[history.length - 1] ?? null;
    this.tickCursorHistory.set(history.slice(0, -1));
    this.tickCursor.set(previousCursor);
    const previousPage = Math.max(0, this.pageIndex() - 1);
    this.pageIndex.set(previousPage);
    this.fetchPage(previousPage, this.pageSize());
  }

  private isDataset(value: unknown): value is PolygonDatasetKey {
    return value === 'day' || value === 'minute' || value === 'second' || value === 'ticks';
  }
}
