import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { timeout } from 'rxjs/operators';
import {
  IPolygonDayAggregate,
  IPolygonMinuteAggregate,
  IPolygonSecondAggregate,
  IPolygonTick,
} from '../../shared/models';

export interface IPagedResponse<T> {
  items: T[];
  total: number | null;
  page: number | null;
  page_size: number;
  trade_date: string | null;
  source?: string;
  latest_available_ts?: string | null;
  is_stale?: boolean;
  next_cursor?: string | null;
  has_more?: boolean;
}

@Injectable({ providedIn: 'root' })
export class PolygonDataApiService {
  private readonly http = inject(HttpClient);

  private buildBaseParams(page: number, pageSize: number, ticker: string, tradeDate: string | null): HttpParams {
    let params = new HttpParams()
      .set('page', String(page))
      .set('page_size', String(pageSize))
      .set('universe_only', 'true');
    if (ticker) {
      params = params.set('ticker', ticker);
    }
    if (tradeDate) {
      params = params.set('trade_date', tradeDate);
    }
    return params;
  }

  loadDayAggregates(page = 0, pageSize = 25, ticker = '', tradeDate: string | null = null): Observable<IPagedResponse<IPolygonDayAggregate>> {
    const params = this.buildBaseParams(page, pageSize, ticker, tradeDate);
    return this.http.get<IPagedResponse<IPolygonDayAggregate>>('/api/polygon/day-aggregates', { params });
  }

  loadMinuteAggregates(page = 0, pageSize = 25, ticker = '', tradeDate: string | null = null, sessionStartEt = ''): Observable<IPagedResponse<IPolygonMinuteAggregate>> {
    let params = this.buildBaseParams(page, pageSize, ticker, tradeDate);
    if (sessionStartEt) {
      params = params.set('session_start_et', sessionStartEt);
    }
    return this.http.get<IPagedResponse<IPolygonMinuteAggregate>>('/api/polygon/minute-aggregates', { params });
  }

  loadMinuteAggregatesHistory(
    page = 0,
    pageSize = 25,
    ticker = '',
    tradeDate: string | null = null,
  ): Observable<IPagedResponse<IPolygonMinuteAggregate>> {
    const params = this.buildBaseParams(page, pageSize, ticker, tradeDate);
    return this.http.get<IPagedResponse<IPolygonMinuteAggregate>>('/api/polygon/history/minute-aggregates', { params });
  }

  loadSecondAggregates(page = 0, pageSize = 25, ticker = '', tradeDate: string | null = null, sessionStartEt = ''): Observable<IPagedResponse<IPolygonSecondAggregate>> {
    let params = this.buildBaseParams(page, pageSize, ticker, tradeDate);
    if (sessionStartEt) {
      params = params.set('session_start_et', sessionStartEt);
    }
    return this.http.get<IPagedResponse<IPolygonSecondAggregate>>('/api/polygon/second-aggregates', { params }).pipe(timeout(15000));
  }

  loadSecondAggregatesHistory(
    page = 0,
    pageSize = 25,
    ticker = '',
    tradeDate: string | null = null,
  ): Observable<IPagedResponse<IPolygonSecondAggregate>> {
    const params = this.buildBaseParams(page, pageSize, ticker, tradeDate);
    return this.http.get<IPagedResponse<IPolygonSecondAggregate>>('/api/polygon/history/second-aggregates', { params }).pipe(timeout(15000));
  }

  loadTicks(page = 0, pageSize = 25, ticker = '', tradeDate: string | null = null, cursor: string | null = null): Observable<IPagedResponse<IPolygonTick>> {
    let params = this.buildBaseParams(page, pageSize, ticker, tradeDate);
    if (cursor) {
      params = params.set('cursor', cursor);
    }
    return this.http.get<IPagedResponse<IPolygonTick>>('/api/polygon/ticks', { params }).pipe(timeout(15000));
  }
}
