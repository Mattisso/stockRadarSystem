import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';
import { IPortfolio, ITrade, ISignal } from '../../shared/models';

export interface DashboardData {
  portfolio: IPortfolio;
  recentTrades: ITrade[];
  activeSignals: ISignal[];
  health: { status: string };
}

@Injectable({ providedIn: 'root' })
export class DashboardApiService {
  private readonly http = inject(HttpClient);

  loadDashboard(): Observable<DashboardData> {
    return forkJoin({
      portfolio: this.http.get<IPortfolio>('/api/portfolio'),
      recentTrades: this.http.get<ITrade[]>('/api/trades', { params: { limit: '5' } }),
      activeSignals: this.http.get<ISignal[]>('/api/signals', { params: { limit: '10' } }),
      health: this.http.get<{ status: string }>('/api/health'),
    });
  }
}
