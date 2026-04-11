import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ICandidateEvent, IDecisionEvent, ISymbolStateLive } from '../../shared/models';

export interface IAggregatePagedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  trade_date?: string | null;
}

@Injectable({ providedIn: 'root' })
export class AggregateDataApiService {
  private readonly http = inject(HttpClient);

  loadSymbolStateLive(
    page = 0,
    pageSize = 25,
    ticker = '',
    candidateStatus = '',
  ): Observable<IAggregatePagedResponse<ISymbolStateLive>> {
    let params = new HttpParams()
      .set('page', String(page))
      .set('page_size', String(pageSize))
      .set('universe_only', 'true');
    if (ticker) {
      params = params.set('ticker', ticker.toUpperCase());
    }
    if (candidateStatus) {
      params = params.set('candidate_status', candidateStatus.toLowerCase());
    }
    return this.http.get<IAggregatePagedResponse<ISymbolStateLive>>('/api/aggregate/symbol-state-live', { params });
  }

  loadCandidateEvents(
    page = 0,
    pageSize = 25,
    ticker = '',
    tradeDate: string | null = null,
    triggerName = '',
  ): Observable<IAggregatePagedResponse<ICandidateEvent>> {
    let params = new HttpParams()
      .set('page', String(page))
      .set('page_size', String(pageSize))
      .set('universe_only', 'true');
    if (ticker) {
      params = params.set('ticker', ticker.toUpperCase());
    }
    if (tradeDate) {
      params = params.set('trade_date', tradeDate);
    }
    if (triggerName) {
      params = params.set('trigger_name', triggerName);
    }
    return this.http.get<IAggregatePagedResponse<ICandidateEvent>>('/api/aggregate/candidate-events', { params });
  }

  loadDecisionEvents(
    page = 0,
    pageSize = 25,
    ticker = '',
    tradeDate: string | null = null,
    decisionType = '',
  ): Observable<IAggregatePagedResponse<IDecisionEvent>> {
    let params = new HttpParams()
      .set('page', String(page))
      .set('page_size', String(pageSize))
      .set('universe_only', 'true');
    if (ticker) {
      params = params.set('ticker', ticker.toUpperCase());
    }
    if (tradeDate) {
      params = params.set('trade_date', tradeDate);
    }
    if (decisionType) {
      params = params.set('decision_type', decisionType.toLowerCase());
    }
    return this.http.get<IAggregatePagedResponse<IDecisionEvent>>('/api/aggregate/decision-events', { params });
  }
}
