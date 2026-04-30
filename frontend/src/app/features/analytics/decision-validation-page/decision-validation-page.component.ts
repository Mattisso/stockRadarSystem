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
import { IDecisionMarketValidationRow } from '../../../shared/models';
import { AnalyticsApiService } from '../analytics-api.service';

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
  readonly summary = signal<Record<string, number>>({});
  readonly rows = signal<IDecisionMarketValidationRow[]>([]);

  readonly columns = [
    'ticker',
    'reason_code',
    'match_status',
    'buy_ts',
    'sell_ts',
    'buy_price_from_event',
    'sell_price_from_event',
    'buy_price_from_market',
    'sell_price_from_market',
    'market_pnl_pct',
  ];
  readonly pageSizeOptions = [25, 50, 100];
  readonly matchedCount = computed(() => this.summary()['MATCHED'] ?? 0);
  readonly noPriorBuyCount = computed(() => this.summary()['NO_PRIOR_BUY'] ?? 0);
  readonly buyBarNotFoundCount = computed(() => this.summary()['BUY_BAR_NOT_FOUND'] ?? 0);
  readonly sellBarNotFoundCount = computed(() => this.summary()['SELL_BAR_NOT_FOUND'] ?? 0);

  constructor() {
    this.reload();
  }

  reload(): void {
    this.pageIndex.set(0);
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

  trackByRow(_: number, row: IDecisionMarketValidationRow): string {
    return `${row.ticker}-${row.sell_id}`;
  }

  private defaultTradeDate(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
}
