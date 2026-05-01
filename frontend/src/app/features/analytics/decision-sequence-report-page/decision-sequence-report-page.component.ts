import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import { IDecisionOutcomeDetail } from '../../../shared/models';
import { AnalyticsApiService } from '../analytics-api.service';

@Component({
  selector: 'app-decision-sequence-report-page',
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
    MatTableModule,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './decision-sequence-report-page.component.html',
  styleUrl: './decision-sequence-report-page.component.scss',
})
export class DecisionSequenceReportPageComponent {
  private readonly api = inject(AnalyticsApiService);
  private readonly destroyRef = inject(DestroyRef);

  readonly tradeDate = signal(this.defaultTradeDate());
  readonly ticker = signal('');
  readonly reasonCode = signal('');
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly rows = signal<IDecisionOutcomeDetail[]>([]);

  readonly columns = [
    'reason_code',
    'ticker',
    'trade_n',
    'sequence_order',
    'buy_ts',
    'sell_ts',
    'buy_price',
    'sell_price',
    'pnl_abs',
    'pnl_pct',
  ];
  readonly total = computed(() => this.rows().length);

  constructor() {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .loadDecisionOutcomeDetails(this.tradeDate().trim(), this.ticker().trim(), this.reasonCode().trim())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: rows => {
          this.rows.set(rows);
          this.loading.set(false);
        },
        error: () => {
          this.rows.set([]);
          this.loading.set(false);
          this.error.set('Failed to load sequence-paired decision rows.');
        },
      });
  }

  trackByRow(_: number, row: IDecisionOutcomeDetail): string {
    return `${row.ticker}-${row.trade_n}-${row.sell_ts}`;
  }

  isInverted(row: IDecisionOutcomeDetail): boolean {
    return Date.parse(row.buy_ts) > Date.parse(row.sell_ts);
  }

  private defaultTradeDate(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
}
