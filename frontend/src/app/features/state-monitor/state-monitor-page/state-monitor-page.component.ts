import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnDestroy, OnInit } from '@angular/core';
import { Store } from '@ngrx/store';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

import { LoadingComponent } from '../../../shared/components/loading/loading.component';
import { StateMonitorTableComponent } from '../state-monitor-table/state-monitor-table.component';
import { StateMonitorActions } from '../+state/state-monitor.actions';
import {
  selectEntriesSortedByStage,
  selectStageDistribution,
  selectStateMonitorError,
  selectStateMonitorLoading,
  selectLastUpdated,
} from '../+state/state-monitor.reducer';

@Component({
  selector: 'app-state-monitor-page',
  standalone: true,
  imports: [DatePipe, MatCardModule, MatIconModule, LoadingComponent, StateMonitorTableComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './state-monitor-page.component.html',
  styleUrl: './state-monitor-page.component.scss',
})
export class StateMonitorPageComponent implements OnInit, OnDestroy {
  private readonly store = inject(Store);
  private readonly lifecycleKeys = ['watching', 'candidate', 'buy', 'hold', 'sold'] as const;

  entries = this.store.selectSignal(selectEntriesSortedByStage);
  distribution = this.store.selectSignal(selectStageDistribution);
  loading = this.store.selectSignal(selectStateMonitorLoading);
  error = this.store.selectSignal(selectStateMonitorError);
  lastUpdated = this.store.selectSignal(selectLastUpdated);

  readonly stages: ReadonlyArray<{ key: (typeof this.lifecycleKeys)[number]; label: string; icon: string }> = [
    { key: 'watching', label: 'Watching', icon: 'visibility' },
    { key: 'candidate', label: 'Candidate', icon: 'star_outline' },
    { key: 'buy', label: 'Buy', icon: 'shopping_cart' },
    { key: 'hold', label: 'Hold', icon: 'pause_circle' },
    { key: 'sold', label: 'Sold', icon: 'sell' },
  ];

  readonly runtimeNote =
    'This page shows the aggregate-driven live lifecycle from Polygon data. Hold is the active-position lock that prevents repeated buys until a sell event fires.';

  readonly emptyStateNote =
    'Zero counts are normal when the market is closed, the runtime was recently restarted, or no symbols currently qualify for aggregate state progression.';

  ngOnInit(): void {
    this.store.dispatch(StateMonitorActions.load());
    this.store.dispatch(StateMonitorActions.startPolling());
  }

  ngOnDestroy(): void {
    this.store.dispatch(StateMonitorActions.stopPolling());
  }

  countForStage(key: (typeof this.lifecycleKeys)[number]): number {
    return this.distribution()[key];
  }
}
