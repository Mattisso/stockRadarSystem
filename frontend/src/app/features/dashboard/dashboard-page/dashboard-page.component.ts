import { Component, ChangeDetectionStrategy, inject, OnInit, OnDestroy } from '@angular/core';
import { Store } from '@ngrx/store';
import { DashboardActions } from '../+state/dashboard.actions';
import {
  selectPortfolio,
  selectRecentTrades,
  selectActiveSignals,
  selectHealthy,
  selectLoading,
  selectError,
  selectLastUpdated,
} from '../+state/dashboard.reducer';
import { PortfolioSummaryWidgetComponent } from '../portfolio-summary-widget/portfolio-summary-widget.component';
import { PositionsWidgetComponent } from '../positions-widget/positions-widget.component';
import { RecentTradesWidgetComponent } from '../recent-trades-widget/recent-trades-widget.component';
import { ActiveSignalsWidgetComponent } from '../active-signals-widget/active-signals-widget.component';
import { SystemStatusWidgetComponent } from '../system-status-widget/system-status-widget.component';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [
    PortfolioSummaryWidgetComponent,
    PositionsWidgetComponent,
    RecentTradesWidgetComponent,
    ActiveSignalsWidgetComponent,
    SystemStatusWidgetComponent,
    LoadingComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard-page.component.html',
  styleUrl: './dashboard-page.component.scss',
})
export class DashboardPageComponent implements OnInit, OnDestroy {
  private readonly store = inject(Store);

  portfolio = this.store.selectSignal(selectPortfolio);
  recentTrades = this.store.selectSignal(selectRecentTrades);
  activeSignals = this.store.selectSignal(selectActiveSignals);
  healthy = this.store.selectSignal(selectHealthy);
  loading = this.store.selectSignal(selectLoading);
  error = this.store.selectSignal(selectError);
  lastUpdated = this.store.selectSignal(selectLastUpdated);

  ngOnInit(): void {
    this.store.dispatch(DashboardActions.loadDashboard());
    this.store.dispatch(DashboardActions.startPolling());
  }

  ngOnDestroy(): void {
    this.store.dispatch(DashboardActions.stopPolling());
  }
}
