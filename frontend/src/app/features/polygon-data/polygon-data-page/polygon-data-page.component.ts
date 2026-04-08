import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
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
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './polygon-data-page.component.html',
  styleUrl: './polygon-data-page.component.scss',
})
export class PolygonDataPageComponent implements OnInit {
  private readonly api = inject(PolygonDataApiService);
  private readonly pageSize = 50;

  ticker = signal('');
  dayAggregates = signal<IPolygonDayAggregate[]>([]);
  minuteAggregates = signal<IPolygonMinuteAggregate[]>([]);
  secondAggregates = signal<IPolygonSecondAggregate[]>([]);
  ticks = signal<IPolygonTick[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);
  dayLoadingMore = signal(false);
  minuteLoadingMore = signal(false);
  secondLoadingMore = signal(false);
  ticksLoadingMore = signal(false);
  dayNextCursor = signal<string | null>(null);
  minuteNextCursor = signal<string | null>(null);
  secondNextCursor = signal<string | null>(null);
  ticksNextCursor = signal<string | null>(null);
  secondAggregatesWarning = signal<string | null>(null);
  ticksWarning = signal<string | null>(null);

  readonly dayColumns = ['trade_date', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly minuteColumns = ['minute_ts', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly secondColumns = ['second_ts', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly tickColumns = ['tick_ts', 'ticker', 'event_type', 'bid', 'ask', 'last', 'volume'];
  readonly filteredDayAggregates = computed(() => this.dayAggregates());
  readonly filteredMinuteAggregates = computed(() => this.minuteAggregates());
  readonly filteredSecondAggregates = computed(() => this.secondAggregates());
  readonly filteredTicks = computed(() => this.ticks());

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.dayNextCursor.set(null);
    this.minuteNextCursor.set(null);
    this.secondNextCursor.set(null);
    this.ticksNextCursor.set(null);
    this.secondAggregatesWarning.set(null);
    this.ticksWarning.set(null);

    let pending = 4;
    const finish = () => {
      pending -= 1;
      if (pending <= 0) {
        this.loading.set(false);
      }
    };
    const requestTicker = this.ticker().trim().toUpperCase();

    this.api.loadDayAggregates(this.pageSize, requestTicker).subscribe({
      next: page => {
        this.dayAggregates.set(page.items);
        this.dayNextCursor.set(page.next_cursor);
        finish();
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Polygon day aggregates');
        finish();
      },
    });

    this.api.loadMinuteAggregates(this.pageSize, requestTicker).subscribe({
      next: page => {
        this.minuteAggregates.set(page.items);
        this.minuteNextCursor.set(page.next_cursor);
        finish();
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Polygon minute aggregates');
        finish();
      },
    });

    this.api.loadSecondAggregates(this.pageSize, requestTicker).subscribe({
      next: page => {
        this.secondAggregates.set(page.items);
        this.secondNextCursor.set(page.next_cursor);
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

    this.api.loadTicks(this.pageSize, requestTicker).subscribe({
      next: page => {
        this.ticks.set(page.items);
        this.ticksNextCursor.set(page.next_cursor);
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

  loadMoreDayAggregates(): void {
    const cursor = this.dayNextCursor();
    if (!cursor || this.dayLoadingMore()) return;
    this.dayLoadingMore.set(true);
    this.api.loadDayAggregates(this.pageSize, this.ticker().trim().toUpperCase(), cursor).subscribe({
      next: page => {
        this.dayAggregates.update(items => [...items, ...page.items]);
        this.dayNextCursor.set(page.next_cursor);
        this.dayLoadingMore.set(false);
      },
      error: () => this.dayLoadingMore.set(false),
    });
  }

  loadMoreMinuteAggregates(): void {
    const cursor = this.minuteNextCursor();
    if (!cursor || this.minuteLoadingMore()) return;
    this.minuteLoadingMore.set(true);
    this.api.loadMinuteAggregates(this.pageSize, this.ticker().trim().toUpperCase(), cursor).subscribe({
      next: page => {
        this.minuteAggregates.update(items => [...items, ...page.items]);
        this.minuteNextCursor.set(page.next_cursor);
        this.minuteLoadingMore.set(false);
      },
      error: () => this.minuteLoadingMore.set(false),
    });
  }

  loadMoreSecondAggregates(): void {
    const cursor = this.secondNextCursor();
    if (!cursor || this.secondLoadingMore()) return;
    this.secondLoadingMore.set(true);
    this.api.loadSecondAggregates(this.pageSize, this.ticker().trim().toUpperCase(), cursor).subscribe({
      next: page => {
        this.secondAggregates.update(items => [...items, ...page.items]);
        this.secondNextCursor.set(page.next_cursor);
        this.secondLoadingMore.set(false);
      },
      error: () => this.secondLoadingMore.set(false),
    });
  }

  loadMoreTicks(): void {
    const cursor = this.ticksNextCursor();
    if (!cursor || this.ticksLoadingMore()) return;
    this.ticksLoadingMore.set(true);
    this.api.loadTicks(this.pageSize, this.ticker().trim().toUpperCase(), cursor).subscribe({
      next: page => {
        this.ticks.update(items => [...items, ...page.items]);
        this.ticksNextCursor.set(page.next_cursor);
        this.ticksLoadingMore.set(false);
      },
      error: () => this.ticksLoadingMore.set(false),
    });
  }
}
