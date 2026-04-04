import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import {
  ISecretL1Candidate,
  ISecretL1ToL2Event,
  ISecretSauceFunnel,
  ISecretUniverseDaily,
} from '../../../shared/models';
import { SecretSauceApiService } from '../secret-sauce-api.service';

@Component({
  selector: 'app-secret-sauce-page',
  standalone: true,
  imports: [LoadingComponent, DatePipe, DecimalPipe, CurrencyPipe, MatCardModule, MatTableModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './secret-sauce-page.component.html',
  styleUrl: './secret-sauce-page.component.scss',
})
export class SecretSaucePageComponent implements OnInit {
  private readonly api = inject(SecretSauceApiService);

  funnel = signal<ISecretSauceFunnel | null>(null);
  universeDaily = signal<ISecretUniverseDaily[]>([]);
  l1Candidates = signal<ISecretL1Candidate[]>([]);
  l1ToL2Events = signal<ISecretL1ToL2Event[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);

  readonly universeColumns = ['trade_date', 'ticker', 'exchange', 'last_price', 'avg_volume', 'created_at'];
  readonly candidateColumns = ['detected_at', 'ticker', 'breakout_score', 'price', 'pct_change_1m', 'volume_ratio', 'reason_flags'];
  readonly handoffColumns = ['escalate_ts', 'ticker', 'latency_ms', 'slot_id', 'escalation_reason'];

  ngOnInit(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.loadOps().subscribe({
      next: data => {
        this.funnel.set(data.funnel);
        this.universeDaily.set(data.universeDaily);
        this.l1Candidates.set(data.l1Candidates);
        this.l1ToL2Events.set(data.l1ToL2Events);
        this.loading.set(false);
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Secret Sauce ops data');
        this.loading.set(false);
      },
    });
  }
}
