import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';
import {
  IKpi,
  IMlStatus,
  ISignalAccuracyBucket,
  IRetrainResponse,
  IDecisionOutcomeDetail,
  IDecisionMarketValidationPage,
  IDecisionRuntimeKpis,
} from '../../shared/models';

export interface AnalyticsData {
  kpis: IKpi;
  mlStatus: IMlStatus;
  signalAccuracy: ISignalAccuracyBucket[];
}

@Injectable({ providedIn: 'root' })
export class AnalyticsApiService {
  private readonly http = inject(HttpClient);

  loadAnalytics(days = 30): Observable<AnalyticsData> {
    return forkJoin({
      kpis: this.http.get<IKpi>('/api/analytics/kpis', { params: { days: String(days) } }),
      mlStatus: this.http.get<IMlStatus>('/api/ml/status'),
      signalAccuracy: this.http.get<ISignalAccuracyBucket[]>('/api/analytics/signal-accuracy'),
    });
  }

  retrain(): Observable<IRetrainResponse> {
    return this.http.post<IRetrainResponse>('/api/ml/retrain', {});
  }

  loadDecisionMarketValidation(
    tradeDate: string,
    page: number,
    pageSize: number,
    ticker?: string,
    reasonCode?: string,
  ): Observable<IDecisionMarketValidationPage> {
    let params = new HttpParams()
      .set('trade_date', tradeDate)
      .set('page', String(page))
      .set('page_size', String(pageSize));
    if (ticker?.trim()) {
      params = params.set('ticker', ticker.trim().toUpperCase());
    }
    if (reasonCode?.trim()) {
      params = params.set('reason_code', reasonCode.trim());
    }
    return this.http.get<IDecisionMarketValidationPage>('/api/analytics/decision-events/market-validation', { params });
  }

  loadDecisionOutcomeDetails(
    tradeDate: string,
    ticker?: string,
    reasonCode?: string,
  ): Observable<IDecisionOutcomeDetail[]> {
    let params = new HttpParams().set('trade_date', tradeDate);
    if (ticker?.trim()) {
      params = params.set('ticker', ticker.trim().toUpperCase());
    }
    if (reasonCode?.trim()) {
      params = params.set('reason_code', reasonCode.trim());
    }
    return this.http.get<IDecisionOutcomeDetail[]>('/api/analytics/decision-events/details', { params });
  }

  loadDecisionRuntimeKpis(windowMinutes = 10): Observable<IDecisionRuntimeKpis> {
    return this.http.get<IDecisionRuntimeKpis>('/api/analytics/runtime-kpis', {
      params: { window_minutes: String(windowMinutes) },
    });
  }
}
