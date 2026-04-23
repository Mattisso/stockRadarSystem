import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe, JsonPipe } from '@angular/common';
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
import { ICandidateEvent, IDecisionEvent, ISymbolStateLive } from '../../../shared/models';
import { AggregateDataApiService } from '../aggregate-data-api.service';

type AggregateDatasetKey = 'live-state' | 'candidate-events' | 'decision-events';

@Component({
  selector: 'app-aggregate-data-page',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    FormsModule,
    JsonPipe,
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
  templateUrl: './aggregate-data-page.component.html',
  styleUrl: './aggregate-data-page.component.scss',
})
export class AggregateDataPageComponent implements OnInit {
  private readonly api = inject(AggregateDataApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  readonly dataset = signal<AggregateDatasetKey>('live-state');
  readonly ticker = signal('');
  readonly tradeDate = signal('');
  readonly secondaryFilter = signal('');
  readonly pageJump = signal('1');
  readonly pageIndex = signal(0);
  readonly pageSize = signal(25);
  readonly total = signal(0);
  readonly resolvedTradeDate = signal<string | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly symbolStates = signal<ISymbolStateLive[]>([]);
  readonly candidateEvents = signal<ICandidateEvent[]>([]);
  readonly decisionEvents = signal<IDecisionEvent[]>([]);
  readonly summary = signal<Record<string, number>>({});

  readonly pageSizeOptions = [10, 25, 50, 100];
  readonly totalPages = computed(() => {
    const total = this.total();
    const size = this.pageSize();
    if (total <= 0 || size <= 0) {
      return 1;
    }
    return Math.ceil(total / size);
  });
  readonly liveStateColumns = [
    'ticker',
    'candidate_status',
    'candidate_score',
    'validation_score',
    'validation_pass_count',
    'rolling_second_high',
    'rolling_second_volume',
    'rolling_green_count',
    'is_second_stream_stale',
    'is_minute_stream_stale',
    'updated_at',
  ];
  readonly candidateEventColumns = [
    'event_ts',
    'ticker',
    'trigger_name',
    'seconds_since_last_trade_bar',
    'minutes_since_last_trade_bar',
    'is_second_stream_stale',
    'is_minute_stream_stale',
  ];
  readonly decisionEventColumns = [
    'decision_ts',
    'ticker',
    'decision_type',
    'reason_code',
    'candidate_score',
    'validation_pass_count',
    'decision_payload',
    'is_second_stream_stale',
    'is_minute_stream_stale',
  ];
  readonly summaryItems = computed(() => {
    if (this.dataset() === 'decision-events') {
      const summary = this.summary();
      return [
        { label: 'Candidate', value: summary['candidate'] ?? 0 },
        { label: 'Buy', value: summary['buy'] ?? 0 },
        { label: 'Manage', value: summary['manage'] ?? 0 },
        { label: 'Sell', value: summary['sell'] ?? 0 },
        { label: 'Reject', value: summary['reject'] ?? 0 },
      ];
    }
    if (this.dataset() === 'candidate-events') {
      const summary = this.summary();
      return [
        { label: 'Events', value: summary['events'] ?? this.total() },
        { label: 'Stale Events', value: summary['stale'] ?? 0 },
        { label: 'Live Events', value: summary['live'] ?? 0 },
      ];
    }
    const summary = this.summary();
    return [
      { label: 'Validated', value: summary['validated'] ?? 0 },
      { label: 'Buy', value: summary['buy'] ?? 0 },
      { label: 'Manage', value: summary['manage'] ?? 0 },
      { label: 'Sold', value: summary['sold'] ?? 0 },
      { label: 'Rejected', value: summary['rejected'] ?? 0 },
      { label: 'Stale', value: summary['stale'] ?? 0 },
    ];
  });

  readonly title = computed(() => {
    switch (this.dataset()) {
      case 'candidate-events':
        return 'Aggregate Candidate Events';
      case 'decision-events':
        return 'Aggregate Decision Events';
      default:
        return 'Aggregate Live Symbol State';
    }
  });
  readonly description = computed(() => {
    switch (this.dataset()) {
      case 'candidate-events':
        return 'Aggregate-only trigger events emitted from stored second bars, paged server-side and filtered by ticker/date.';
      case 'decision-events':
        return 'Explicit aggregate-only lifecycle decisions showing which candidates were validated or rejected and why.';
      default:
        return 'One row per under-$10 universe symbol showing freshness, rolling-second state, candidate status, and validation state.';
    }
  });
  readonly secondaryLabel = computed(() => {
    switch (this.dataset()) {
      case 'candidate-events':
        return 'Trigger name';
      case 'decision-events':
        return 'Decision type';
      default:
        return 'Candidate status';
    }
  });
  readonly secondaryPlaceholder = computed(() => {
    switch (this.dataset()) {
      case 'candidate-events':
        return 'breakout_above_recent_high';
      case 'decision-events':
        return 'candidate';
      default:
        return 'validated';
    }
  });
  readonly showTradeDateFilter = computed(() => this.dataset() !== 'live-state');

  ngOnInit(): void {
    this.route.data.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(data => {
      const routeDataset = data['dataset'];
      this.dataset.set(this.isDataset(routeDataset) ? routeDataset : 'live-state');
      this.secondaryFilter.set('');
      this.tradeDate.set('');
      this.reload();
    });
  }

  reload(): void {
    this.pageIndex.set(0);
    this.pageJump.set('1');
    this.fetchPage(0, this.pageSize());
  }

  onPage(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.pageJump.set(String(event.pageIndex + 1));
    this.fetchPage(event.pageIndex, event.pageSize);
  }

  onPageJump(): void {
    const requestedPage = Number.parseInt(this.pageJump().trim(), 10);
    if (!Number.isFinite(requestedPage)) {
      this.pageJump.set(String(this.pageIndex() + 1));
      return;
    }
    const clampedPage = Math.min(Math.max(requestedPage, 1), this.totalPages());
    const zeroBasedPage = clampedPage - 1;
    this.pageIndex.set(zeroBasedPage);
    this.pageJump.set(String(clampedPage));
    this.fetchPage(zeroBasedPage, this.pageSize());
  }

  private fetchPage(page: number, pageSize: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.symbolStates.set([]);
    this.candidateEvents.set([]);
    this.decisionEvents.set([]);
    this.summary.set({});

    const ticker = this.ticker().trim().toUpperCase();
    const secondaryFilter = this.secondaryFilter().trim();
    const tradeDate = this.tradeDate().trim() || null;

    if (this.dataset() === 'decision-events') {
      this.api.loadDecisionEvents(page, pageSize, ticker, tradeDate, secondaryFilter).subscribe({
        next: response => {
          this.decisionEvents.set(response.items);
          this.total.set(response.total);
          this.pageJump.set(String(page + 1));
          this.summary.set(response.summary ?? {});
          this.resolvedTradeDate.set(response.trade_date ?? null);
          this.loading.set(false);
        },
        error: () => this.handleError('Failed to load aggregate decision events.'),
      });
      return;
    }

    if (this.dataset() === 'candidate-events') {
      this.api.loadCandidateEvents(page, pageSize, ticker, tradeDate, secondaryFilter).subscribe({
        next: response => {
          this.candidateEvents.set(response.items);
          this.total.set(response.total);
          this.pageJump.set(String(page + 1));
          this.summary.set(response.summary ?? {});
          this.resolvedTradeDate.set(response.trade_date ?? null);
          this.loading.set(false);
        },
        error: () => this.handleError('Failed to load aggregate candidate events.'),
      });
      return;
    }

    this.api.loadSymbolStateLive(page, pageSize, ticker, secondaryFilter).subscribe({
      next: response => {
        this.symbolStates.set(response.items);
        this.total.set(response.total);
        this.pageJump.set(String(page + 1));
        this.summary.set(response.summary ?? {});
        this.resolvedTradeDate.set(null);
        this.loading.set(false);
      },
      error: () => this.handleError('Failed to load aggregate live symbol state.'),
    });
  }

  private handleError(message: string): void {
    this.error.set(message);
    this.total.set(0);
    this.loading.set(false);
  }

  previewDecisionPayload(payload: string | null): string {
    if (!payload) {
      return '-';
    }
    if (payload.length <= 80) {
      return payload;
    }
    return `${payload.slice(0, 77)}...`;
  }

  badgeClass(value: string | null | undefined, kind: 'decision' | 'status'): string {
    const normalized = (value ?? '').toLowerCase();
    if (!normalized) {
      return 'badge badge-neutral';
    }
    if (normalized === 'buy') {
      return 'badge badge-buy';
    }
    if (normalized === 'manage') {
      return 'badge badge-manage';
    }
    if (normalized === 'sell' || normalized === 'sold') {
      return 'badge badge-sell';
    }
    if (normalized === 'candidate' || normalized === 'validated') {
      return 'badge badge-candidate';
    }
    if (normalized === 'reject' || normalized === 'rejected') {
      return 'badge badge-reject';
    }
    return kind === 'decision' ? 'badge badge-neutral' : 'badge badge-neutral';
  }

  private isDataset(value: unknown): value is AggregateDatasetKey {
    return value === 'live-state' || value === 'candidate-events' || value === 'decision-events';
  }
}
