import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, timeout } from 'rxjs/operators';
import {
  IPolygonDayAggregate,
  IPolygonMinuteAggregate,
  IPolygonSecondAggregate,
  IPolygonTick,
} from '../../shared/models';

export interface IPagedResponse<T> {
  items: T[];
  next_cursor: string | null;
}

@Injectable({ providedIn: 'root' })
export class PolygonDataApiService {
  private readonly http = inject(HttpClient);

  private buildBaseParams(limit: number, ticker: string): HttpParams {
    let params = new HttpParams()
      .set('limit', String(limit))
      .set('universe_only', 'true');
    if (ticker) {
      params = params.set('ticker', ticker);
    }
    return params;
  }

  loadDayAggregates(limit = 50, ticker = '', afterTicker: string | null = null): Observable<IPagedResponse<IPolygonDayAggregate>> {
    let params = this.buildBaseParams(limit, ticker);
    if (afterTicker) {
      params = params.set('after_ticker', afterTicker);
    }
    return this.http.get<IPagedResponse<IPolygonDayAggregate>>('/api/polygon/day-aggregates', { params });
  }

  loadMinuteAggregates(limit = 50, ticker = '', beforeMinuteTs: string | null = null): Observable<IPagedResponse<IPolygonMinuteAggregate>> {
    let params = this.buildBaseParams(limit, ticker);
    if (beforeMinuteTs) {
      params = params.set('before_minute_ts', beforeMinuteTs);
    }
    return this.http.get<IPagedResponse<IPolygonMinuteAggregate>>('/api/polygon/minute-aggregates', { params });
  }

  loadSecondAggregates(limit = 50, ticker = '', beforeSecondTs: string | null = null): Observable<IPagedResponse<IPolygonSecondAggregate>> {
    let params = this.buildBaseParams(limit, ticker);
    if (beforeSecondTs) {
      params = params.set('before_second_ts', beforeSecondTs);
    }
    return this.http.get<IPagedResponse<IPolygonSecondAggregate>>('/api/polygon/second-aggregates', { params }).pipe(
      timeout(10000),
      catchError(() => of({ items: [], next_cursor: null })),
    );
  }

  loadTicks(limit = 50, ticker = '', cursor: string | null = null): Observable<IPagedResponse<IPolygonTick>> {
    let params = this.buildBaseParams(limit, ticker);
    if (cursor) {
      const [beforeTickTs, beforeId] = cursor.split('|');
      params = params.set('before_tick_ts', beforeTickTs);
      params = params.set('before_id', beforeId);
    }
    return this.http.get<IPagedResponse<IPolygonTick>>('/api/polygon/ticks', { params }).pipe(
      timeout(10000),
      catchError(() => of({ items: [], next_cursor: null })),
    );
  }
}
