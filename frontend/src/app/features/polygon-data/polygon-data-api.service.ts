import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, forkJoin, of } from 'rxjs';
import { catchError, map, timeout } from 'rxjs/operators';
import {
  IPolygonDayAggregate,
  IPolygonMinuteAggregate,
  IPolygonSecondAggregate,
  IPolygonTick,
} from '../../shared/models';

export interface PolygonDataOpsData {
  dayAggregates: IPolygonDayAggregate[];
  minuteAggregates: IPolygonMinuteAggregate[];
  secondAggregates: IPolygonSecondAggregate[];
  ticks: IPolygonTick[];
  ticksWarning: string | null;
}

@Injectable({ providedIn: 'root' })
export class PolygonDataApiService {
  private readonly http = inject(HttpClient);

  loadOps(limit = 100, ticker = ''): Observable<PolygonDataOpsData> {
    let params = new HttpParams()
      .set('limit', String(limit))
      .set('universe_only', 'true');
    if (ticker) {
      params = params.set('ticker', ticker);
    }
    return forkJoin({
      dayAggregates: this.http.get<IPolygonDayAggregate[]>('/api/polygon/day-aggregates', { params }),
      minuteAggregates: this.http.get<IPolygonMinuteAggregate[]>('/api/polygon/minute-aggregates', { params }),
      secondAggregates: this.http.get<IPolygonSecondAggregate[]>('/api/polygon/second-aggregates', { params }),
      ticksResult: this.http.get<IPolygonTick[]>('/api/polygon/ticks', { params }).pipe(
        timeout(10000),
        map(ticks => ({ ticks, ticksWarning: null as string | null })),
        catchError(() =>
          of({
            ticks: [] as IPolygonTick[],
            ticksWarning: 'Live ticks are temporarily unavailable or too slow to load.',
          })
        ),
      ),
    }).pipe(
      map(({ dayAggregates, minuteAggregates, secondAggregates, ticksResult }) => ({
        dayAggregates,
        minuteAggregates,
        secondAggregates,
        ticks: ticksResult.ticks,
        ticksWarning: ticksResult.ticksWarning,
      })),
    });
  }
}
