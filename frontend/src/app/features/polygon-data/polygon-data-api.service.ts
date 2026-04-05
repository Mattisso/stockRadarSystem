import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';
import { IPolygonDayAggregate, IPolygonMinuteAggregate, IPolygonTick } from '../../shared/models';

export interface PolygonDataOpsData {
  dayAggregates: IPolygonDayAggregate[];
  minuteAggregates: IPolygonMinuteAggregate[];
  ticks: IPolygonTick[];
}

@Injectable({ providedIn: 'root' })
export class PolygonDataApiService {
  private readonly http = inject(HttpClient);

  loadOps(limit = 100, ticker = ''): Observable<PolygonDataOpsData> {
    const params = ticker ? { limit: String(limit), ticker } : { limit: String(limit) };
    return forkJoin({
      dayAggregates: this.http.get<IPolygonDayAggregate[]>('/api/polygon/day-aggregates', { params }),
      minuteAggregates: this.http.get<IPolygonMinuteAggregate[]>('/api/polygon/minute-aggregates', { params }),
      ticks: this.http.get<IPolygonTick[]>('/api/polygon/ticks', { params }),
    });
  }
}
