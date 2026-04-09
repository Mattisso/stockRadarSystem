import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import {
  IPolygonDayAggregate,
  IPolygonMinuteAggregate,
  IPolygonSecondAggregate,
  IPolygonTick,
} from '../../../shared/models';
import { PolygonDataApiService } from '../polygon-data-api.service';

@Component({
  selector: 'app-polygon-data-page',
  standalone: true,
  imports: [
    LoadingComponent,
    DatePipe,
    DecimalPipe,
    FormsModule,
    MatCardModule,
    MatTableModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatPaginatorModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './polygon-data-page.component.html',
  styleUrl: './polygon-data-page.component.scss',
})
export class PolygonDataPageComponent implements OnInit {
  private readonly api = inject(PolygonDataApiService);

  ticker = signal('');
  tradeDate = signal('');
  dayAggregates = signal<IPolygonDayAggregate[]>([]);
  minuteAggregates = signal<IPolygonMinuteAggregate[]>([]);
  secondAggregates = signal<IPolygonSecondAggregate[]>([]);
  ticks = signal<IPolygonTick[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);
  secondAggregatesWarning = signal<string | null>(null);
  ticksWarning = signal<string | null>(null);
  dayTotal = signal(0);
  minuteTotal = signal(0);
  secondTotal = signal(0);
  tickTotal = signal(0);
  dayPageIndex = signal(0);
  minutePageIndex = signal(0);
  secondPageIndex = signal(0);
  tickPageIndex = signal(0);
  dayPageSize = signal(25);
  minutePageSize = signal(25);
  secondPageSize = signal(25);
  tickPageSize = signal(25);
  dayTradeDate = signal<string | null>(null);
  minuteTradeDate = signal<string | null>(null);
  secondTradeDate = signal<string | null>(null);
  tickTradeDate = signal<string | null>(null);

  readonly dayColumns = ['trade_date', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly minuteColumns = ['minute_ts', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly secondColumns = ['second_ts', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly tickColumns = ['tick_ts', 'ticker', 'event_type', 'bid', 'ask', 'last', 'volume'];
  readonly pageSizeOptions = [10, 25, 50, 100];
  readonly requestTicker = computed(() => this.ticker().trim().toUpperCase());
  readonly requestTradeDate = computed(() => this.tradeDate().trim() || null);

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.secondAggregatesWarning.set(null);
    this.ticksWarning.set(null);
    this.dayPageIndex.set(0);
    this.minutePageIndex.set(0);
    this.secondPageIndex.set(0);
    this.tickPageIndex.set(0);

    let pending = 4;
    const finish = () => {
      pending -= 1;
      if (pending <= 0) {
        this.loading.set(false);
      }
    };
    const requestTicker = this.requestTicker();
    const requestTradeDate = this.requestTradeDate();

    this.api.loadDayAggregates(0, this.dayPageSize(), requestTicker, requestTradeDate).subscribe({
      next: page => {
        this.dayAggregates.set(page.items);
        this.dayTotal.set(page.total);
        this.dayTradeDate.set(page.trade_date);
        finish();
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Polygon day aggregates');
        finish();
      },
    });

    this.api.loadMinuteAggregates(0, this.minutePageSize(), requestTicker, requestTradeDate).subscribe({
      next: page => {
        this.minuteAggregates.set(page.items);
        this.minuteTotal.set(page.total);
        this.minuteTradeDate.set(page.trade_date);
        finish();
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Polygon minute aggregates');
        finish();
      },
    });

    this.api.loadSecondAggregates(0, this.secondPageSize(), requestTicker, requestTradeDate).subscribe({
      next: page => {
        this.secondAggregates.set(page.items);
        this.secondTotal.set(page.total);
        this.secondTradeDate.set(page.trade_date);
        this.secondAggregatesWarning.set(
          !page.items.length ? 'Second aggregates are temporarily unavailable or too slow to load.' : null,
        );
        finish();
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Polygon second aggregates');
        finish();
      },
    });

    this.api.loadTicks(0, this.tickPageSize(), requestTicker, requestTradeDate).subscribe({
      next: page => {
        this.ticks.set(page.items);
        this.tickTotal.set(page.total);
        this.tickTradeDate.set(page.trade_date);
        this.ticksWarning.set(
          !page.items.length ? 'Live ticks are temporarily unavailable or too slow to load.' : null,
        );
        finish();
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Polygon ticks');
        finish();
      },
    });
  }

  onDayPage(event: PageEvent): void {
    this.dayPageIndex.set(event.pageIndex);
    this.dayPageSize.set(event.pageSize);
    this.api.loadDayAggregates(event.pageIndex, event.pageSize, this.requestTicker(), this.requestTradeDate()).subscribe({
      next: page => {
        this.dayAggregates.set(page.items);
        this.dayTotal.set(page.total);
        this.dayTradeDate.set(page.trade_date);
      },
    });
  }

  onMinutePage(event: PageEvent): void {
    this.minutePageIndex.set(event.pageIndex);
    this.minutePageSize.set(event.pageSize);
    this.api.loadMinuteAggregates(event.pageIndex, event.pageSize, this.requestTicker(), this.requestTradeDate()).subscribe({
      next: page => {
        this.minuteAggregates.set(page.items);
        this.minuteTotal.set(page.total);
        this.minuteTradeDate.set(page.trade_date);
      },
    });
  }

  onSecondPage(event: PageEvent): void {
    this.secondPageIndex.set(event.pageIndex);
    this.secondPageSize.set(event.pageSize);
    this.api.loadSecondAggregates(event.pageIndex, event.pageSize, this.requestTicker(), this.requestTradeDate()).subscribe({
      next: page => {
        this.secondAggregates.set(page.items);
        this.secondTotal.set(page.total);
        this.secondTradeDate.set(page.trade_date);
        this.secondAggregatesWarning.set(
          !page.items.length ? 'Second aggregates are temporarily unavailable or too slow to load.' : null,
        );
      },
    });
  }

  onTickPage(event: PageEvent): void {
    this.tickPageIndex.set(event.pageIndex);
    this.tickPageSize.set(event.pageSize);
    this.api.loadTicks(event.pageIndex, event.pageSize, this.requestTicker(), this.requestTradeDate()).subscribe({
      next: page => {
        this.ticks.set(page.items);
        this.tickTotal.set(page.total);
        this.tickTradeDate.set(page.trade_date);
        this.ticksWarning.set(
          !page.items.length ? 'Live ticks are temporarily unavailable or too slow to load.' : null,
        );
      },
    });
  }
}
