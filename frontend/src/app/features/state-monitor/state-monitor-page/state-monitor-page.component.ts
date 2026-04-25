import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
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

const STATE_MONITOR_LIFECYCLE_KEYS = ['watching', 'candidate', 'buy', 'manage', 'sold', 'rejected'] as const;
type StateMonitorLifecycleKey = (typeof STATE_MONITOR_LIFECYCLE_KEYS)[number];

@Component({
  selector: 'app-state-monitor-page',
  standalone: true,
  imports: [DatePipe, FormsModule, MatCardModule, MatIconModule, LoadingComponent, StateMonitorTableComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './state-monitor-page.component.html',
  styleUrl: './state-monitor-page.component.scss',
})
export class StateMonitorPageComponent implements OnInit, OnDestroy {
  private readonly store = inject(Store);

  entries = this.store.selectSignal(selectEntriesSortedByStage);
  distribution = this.store.selectSignal(selectStageDistribution);
  loading = this.store.selectSignal(selectStateMonitorLoading);
  error = this.store.selectSignal(selectStateMonitorError);
  lastUpdated = this.store.selectSignal(selectLastUpdated);
  pageSize = signal(25);
  currentPage = signal(1);
  pageJump = signal<string | number>('1');

  readonly stages: ReadonlyArray<{ key: StateMonitorLifecycleKey; label: string; icon: string }> = [
    { key: 'watching', label: 'Watching', icon: 'visibility' },
    { key: 'candidate', label: 'Candidate', icon: 'star_outline' },
    { key: 'buy', label: 'Buy', icon: 'shopping_cart' },
    { key: 'manage', label: 'Manage', icon: 'pause_circle' },
    { key: 'sold', label: 'Sold', icon: 'sell' },
    { key: 'rejected', label: 'Rejected', icon: 'block' },
  ];

  readonly runtimeNote =
    'This page shows the aggregate-driven live lifecycle from Polygon data. Repeated buys are suppressed while a symbol remains in buy/manage until a sell event fires.';

  readonly emptyStateNote =
    'Zero counts are normal when the market is closed, the runtime was recently restarted, or no symbols currently qualify for aggregate state progression.';
  readonly totalPages = computed(() => {
    const total = this.entries().length;
    return Math.max(1, Math.ceil(total / this.pageSize()));
  });
  readonly pagedEntries = computed(() => {
    const page = Math.min(this.currentPage(), this.totalPages());
    const start = (page - 1) * this.pageSize();
    return this.entries().slice(start, start + this.pageSize());
  });
  readonly pageSizeOptions = [25, 50, 100];

  ngOnInit(): void {
    this.store.dispatch(StateMonitorActions.load());
    this.store.dispatch(StateMonitorActions.startPolling());
  }

  ngOnDestroy(): void {
    this.store.dispatch(StateMonitorActions.stopPolling());
  }

  countForStage(key: StateMonitorLifecycleKey): number {
    return this.distribution()[key];
  }

  updatePageSize(value: number | string): void {
    this.pageSize.set(Number(value));
    this.currentPage.set(1);
    this.pageJump.set('1');
  }

  previousPage(): void {
    if (this.currentPage() > 1) {
      const next = this.currentPage() - 1;
      this.currentPage.set(next);
      this.pageJump.set(String(next));
    }
  }

  nextPage(): void {
    if (this.currentPage() < this.totalPages()) {
      const next = this.currentPage() + 1;
      this.currentPage.set(next);
      this.pageJump.set(String(next));
    }
  }

  goToFirstPage(): void {
    this.currentPage.set(1);
    this.pageJump.set('1');
  }

  goToLastPage(): void {
    const last = this.totalPages();
    this.currentPage.set(last);
    this.pageJump.set(String(last));
  }

  onPageJump(): void {
    const requestedPage = Number.parseInt(String(this.pageJump()).trim(), 10);
    if (!Number.isFinite(requestedPage)) {
      this.pageJump.set(String(this.currentPage()));
      return;
    }
    const clampedPage = Math.min(Math.max(requestedPage, 1), this.totalPages());
    this.currentPage.set(clampedPage);
    this.pageJump.set(String(clampedPage));
  }
}
