import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ISymbolStateLive } from '../../shared/models/aggregate-data.model';

export interface IStateMonitorResponse {
  items: ISymbolStateLive[];
  total: number;
  page: number;
  page_size: number;
  summary: Record<string, number>;
}

@Injectable({ providedIn: 'root' })
export class StateMonitorApiService {
  private readonly http = inject(HttpClient);

  getAll(): Observable<IStateMonitorResponse> {
    return this.http.get<IStateMonitorResponse>('/api/aggregate/symbol-state-live?page=0&page_size=250');
  }
}
