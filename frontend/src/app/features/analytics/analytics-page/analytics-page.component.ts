import { Component, ChangeDetectionStrategy, inject, OnInit } from '@angular/core';
import { Store } from '@ngrx/store';
import { AnalyticsActions } from '../+state/analytics.actions';
import {
  selectKpis,
  selectMlStatus,
  selectSignalAccuracy,
  selectLoading,
  selectRetraining,
  selectError,
} from '../+state/analytics.reducer';
import { KpiWidgetComponent } from '../kpi-widget/kpi-widget.component';
import { MlStatusWidgetComponent } from '../ml-status-widget/ml-status-widget.component';
import { SignalAccuracyWidgetComponent } from '../signal-accuracy-widget/signal-accuracy-widget.component';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';

@Component({
  selector: 'app-analytics-page',
  standalone: true,
  imports: [
    KpiWidgetComponent,
    MlStatusWidgetComponent,
    SignalAccuracyWidgetComponent,
    LoadingComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './analytics-page.component.html',
  styleUrl: './analytics-page.component.scss',
})
export class AnalyticsPageComponent implements OnInit {
  private readonly store = inject(Store);

  kpis = this.store.selectSignal(selectKpis);
  mlStatus = this.store.selectSignal(selectMlStatus);
  signalAccuracy = this.store.selectSignal(selectSignalAccuracy);
  loading = this.store.selectSignal(selectLoading);
  retraining = this.store.selectSignal(selectRetraining);
  error = this.store.selectSignal(selectError);

  ngOnInit(): void {
    this.store.dispatch(AnalyticsActions.loadAnalytics());
  }

  onRetrain(): void {
    this.store.dispatch(AnalyticsActions.retrainModel());
  }
}
