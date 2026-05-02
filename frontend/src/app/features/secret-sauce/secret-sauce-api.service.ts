import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  IL2Health,
  ISecretL1Candidate,
  ISecretL1ToL2Event,
  ISecretSauceFunnel,
  ISecretUniverseDaily,
} from '../../shared/models';

@Injectable({ providedIn: 'root' })
export class SecretSauceApiService {
  private readonly http = inject(HttpClient);

  getFunnel(): Observable<ISecretSauceFunnel> {
    return this.http.get<ISecretSauceFunnel>('/api/secret-sauce/funnel');
  }

  getL2Health(): Observable<IL2Health> {
    return this.http.get<IL2Health>('/api/health/l2');
  }

  getUniverseDaily(limit = 100): Observable<ISecretUniverseDaily[]> {
    return this.http.get<ISecretUniverseDaily[]>('/api/secret-sauce/universe-daily', {
      params: { limit: String(limit) },
    });
  }

  downloadFlatfile(tradeDate: string): Observable<Blob> {
    return this.http.get('/api/secret-sauce/flatfile-download', {
      params: { trade_date: tradeDate },
      responseType: 'blob',
    });
  }

  getL1Candidates(limit = 100): Observable<ISecretL1Candidate[]> {
    return this.http.get<ISecretL1Candidate[]>('/api/secret-sauce/l1-candidates', {
      params: { limit: String(limit) },
    });
  }

  getL1ToL2Events(limit = 100): Observable<ISecretL1ToL2Event[]> {
    return this.http.get<ISecretL1ToL2Event[]>('/api/secret-sauce/l1-to-l2-events', {
      params: { limit: String(limit) },
    });
  }
}
