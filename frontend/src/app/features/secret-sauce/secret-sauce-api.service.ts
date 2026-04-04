import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';
import { ISecretL1Candidate, ISecretL1ToL2Event, ISecretUniverseDaily } from '../../shared/models';

export interface SecretSauceOpsData {
  universeDaily: ISecretUniverseDaily[];
  l1Candidates: ISecretL1Candidate[];
  l1ToL2Events: ISecretL1ToL2Event[];
}

@Injectable({ providedIn: 'root' })
export class SecretSauceApiService {
  private readonly http = inject(HttpClient);

  loadOps(limit = 100): Observable<SecretSauceOpsData> {
    return forkJoin({
      universeDaily: this.http.get<ISecretUniverseDaily[]>('/api/secret-sauce/universe-daily', {
        params: { limit: String(limit) },
      }),
      l1Candidates: this.http.get<ISecretL1Candidate[]>('/api/secret-sauce/l1-candidates', {
        params: { limit: String(limit) },
      }),
      l1ToL2Events: this.http.get<ISecretL1ToL2Event[]>('/api/secret-sauce/l1-to-l2-events', {
        params: { limit: String(limit) },
      }),
    });
  }
}
