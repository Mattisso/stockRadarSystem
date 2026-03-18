import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';
import { IKpi, IMlStatus, ISignalAccuracyBucket, IRetrainResponse } from '../../shared/models';

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
}
