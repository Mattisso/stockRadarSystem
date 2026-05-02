import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import {
  IL2Health,
  ISecretL1Candidate,
  ISecretL1ToL2Event,
  ISecretSauceFunnel,
  ISecretUniverseDaily,
} from '../../../shared/models';
import { SecretSauceApiService } from '../secret-sauce-api.service';

@Component({
  selector: 'app-secret-sauce-page',
  standalone: true,
  imports: [
    LoadingComponent,
    DatePipe,
    DecimalPipe,
    CurrencyPipe,
    FormsModule,
    MatCardModule,
    MatTableModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './secret-sauce-page.component.html',
  styleUrl: './secret-sauce-page.component.scss',
})
export class SecretSaucePageComponent implements OnInit {
  private readonly api = inject(SecretSauceApiService);
  private readonly defaultLimit = 100;

  funnel = signal<ISecretSauceFunnel | null>(null);
  l2Health = signal<IL2Health | null>(null);
  universeDaily = signal<ISecretUniverseDaily[]>([]);
  l1Candidates = signal<ISecretL1Candidate[]>([]);
  l1ToL2Events = signal<ISecretL1ToL2Event[]>([]);
  tickerFilter = signal('');
  flatfileTradeDate = signal(this.defaultTradeDate());
  readonly funnelLoading = signal(false);
  readonly l2Loading = signal(false);
  readonly universeLoading = signal(false);
  readonly candidatesLoading = signal(false);
  readonly handoffLoading = signal(false);
  readonly flatfileDownloading = signal(false);
  readonly funnelError = signal<string | null>(null);
  readonly l2Error = signal<string | null>(null);
  readonly universeError = signal<string | null>(null);
  readonly candidatesError = signal<string | null>(null);
  readonly handoffError = signal<string | null>(null);
  readonly flatfileError = signal<string | null>(null);
  readonly loading = computed(
    () =>
      this.funnelLoading() ||
      this.l2Loading() ||
      this.universeLoading() ||
      this.candidatesLoading() ||
      this.handoffLoading(),
  );
  readonly hasAnyData = computed(
    () =>
      this.funnel() !== null ||
      this.l2Health() !== null ||
      this.universeDaily().length > 0 ||
      this.l1Candidates().length > 0 ||
      this.l1ToL2Events().length > 0,
  );
  readonly pageError = computed(() => {
    if (this.hasAnyData()) {
      return null;
    }

    return (
      this.funnelError() ||
      this.l2Error() ||
      this.universeError() ||
      this.candidatesError() ||
      this.handoffError()
    );
  });

  readonly universeColumns = ['trade_date', 'ticker', 'exchange', 'last_price', 'avg_volume', 'created_at'];
  readonly candidateColumns = ['detected_at', 'ticker', 'breakout_score', 'price', 'pct_change_1m', 'volume_ratio', 'reason_flags'];
  readonly handoffColumns = ['escalate_ts', 'ticker', 'latency_ms', 'slot_id', 'escalation_reason'];
  readonly l2Columns = ['ticker', 'confirmed', 'has_depth', 'bid_levels', 'ask_levels'];

  readonly filteredUniverseDaily = computed(() => this.filterByTicker(this.universeDaily(), row => row.ticker));
  readonly filteredL1Candidates = computed(() => this.filterByTicker(this.l1Candidates(), row => row.ticker));
  readonly filteredL1ToL2Events = computed(() => this.filterByTicker(this.l1ToL2Events(), row => row.ticker));
  readonly filteredL2Subscriptions = computed(() =>
    this.filterByTicker(this.l2Health()?.subscriptions ?? [], row => row.ticker),
  );

  ngOnInit(): void {
    this.loadFunnel();
    this.loadL2Health();
    this.loadUniverseDaily();
    this.loadL1Candidates();
    this.loadL1ToL2Events();
  }

  private filterByTicker<T>(rows: T[], tickerSelector: (row: T) => string): T[] {
    const filter = this.tickerFilter().trim().toUpperCase();
    if (!filter) {
      return rows;
    }
    return rows.filter(row => tickerSelector(row).toUpperCase().includes(filter));
  }

  downloadFlatfile(): void {
    const tradeDate = this.flatfileTradeDate().trim();
    if (!tradeDate) {
      this.flatfileError.set('Select a trade date before downloading the flatfile.');
      return;
    }

    this.flatfileDownloading.set(true);
    this.flatfileError.set(null);
    this.api.downloadFlatfile(tradeDate).subscribe({
      next: blob => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${tradeDate}.csv.gz`;
        anchor.click();
        URL.revokeObjectURL(url);
        this.flatfileDownloading.set(false);
      },
      error: error => {
        this.flatfileError.set(this.toErrorMessage(error, 'Failed to download Polygon flatfile'));
        this.flatfileDownloading.set(false);
      },
    });
  }

  private loadFunnel(): void {
    this.funnelLoading.set(true);
    this.funnelError.set(null);
    this.api.getFunnel().subscribe({
      next: data => {
        this.funnel.set(data);
        if (data.trade_date) {
          this.flatfileTradeDate.set(data.trade_date);
        }
        this.funnelLoading.set(false);
      },
      error: error => {
        this.funnelError.set(this.toErrorMessage(error, 'Failed to load funnel summary'));
        this.funnelLoading.set(false);
      },
    });
  }

  private loadL2Health(): void {
    this.l2Loading.set(true);
    this.l2Error.set(null);
    this.api.getL2Health().subscribe({
      next: data => {
        this.l2Health.set(data);
        this.l2Loading.set(false);
      },
      error: error => {
        this.l2Error.set(this.toErrorMessage(error, 'Failed to load L2 health'));
        this.l2Loading.set(false);
      },
    });
  }

  private loadUniverseDaily(): void {
    this.universeLoading.set(true);
    this.universeError.set(null);
    this.api.getUniverseDaily(this.defaultLimit).subscribe({
      next: data => {
        this.universeDaily.set(data);
        this.universeLoading.set(false);
      },
      error: error => {
        this.universeError.set(this.toErrorMessage(error, 'Failed to load universe snapshots'));
        this.universeLoading.set(false);
      },
    });
  }

  private loadL1Candidates(): void {
    this.candidatesLoading.set(true);
    this.candidatesError.set(null);
    this.api.getL1Candidates(this.defaultLimit).subscribe({
      next: data => {
        this.l1Candidates.set(data);
        this.candidatesLoading.set(false);
      },
      error: error => {
        this.candidatesError.set(this.toErrorMessage(error, 'Failed to load L1 candidates'));
        this.candidatesLoading.set(false);
      },
    });
  }

  private loadL1ToL2Events(): void {
    this.handoffLoading.set(true);
    this.handoffError.set(null);
    this.api.getL1ToL2Events(this.defaultLimit).subscribe({
      next: data => {
        this.l1ToL2Events.set(data);
        this.handoffLoading.set(false);
      },
      error: error => {
        this.handoffError.set(this.toErrorMessage(error, 'Failed to load L1 to L2 events'));
        this.handoffLoading.set(false);
      },
    });
  }

  private toErrorMessage(error: unknown, fallback: string): string {
    if (typeof error === 'object' && error !== null && 'message' in error && typeof error.message === 'string') {
      return error.message;
    }
    return fallback;
  }

  private defaultTradeDate(): string {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/New_York',
    }).format(new Date());
  }
}
