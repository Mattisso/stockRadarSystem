import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import { IPolygonDayAggregate, IPolygonMinuteAggregate, IPolygonTick } from '../../../shared/models';
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

  ticker = signal('');
  dayAggregates = signal<IPolygonDayAggregate[]>([]);
  minuteAggregates = signal<IPolygonMinuteAggregate[]>([]);
  ticks = signal<IPolygonTick[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);

  readonly dayColumns = ['trade_date', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly minuteColumns = ['minute_ts', 'ticker', 'open', 'high', 'low', 'close', 'volume'];
  readonly tickColumns = ['tick_ts', 'ticker', 'event_type', 'bid', 'ask', 'last', 'volume'];
  readonly filteredDayAggregates = computed(() => this.dayAggregates());
  readonly filteredMinuteAggregates = computed(() => this.minuteAggregates());
  readonly filteredTicks = computed(() => this.ticks());

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.loadOps(100, this.ticker().trim().toUpperCase()).subscribe({
      next: data => {
        this.dayAggregates.set(data.dayAggregates);
        this.minuteAggregates.set(data.minuteAggregates);
        this.ticks.set(data.ticks);
        this.loading.set(false);
      },
      error: error => {
        this.error.set(error.message ?? 'Failed to load Polygon data');
        this.loading.set(false);
      },
    });
  }
}
