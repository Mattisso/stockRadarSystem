import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ITrade } from '../../shared/models';

@Injectable({ providedIn: 'root' })
export class TradesApiService {
  private readonly http = inject(HttpClient);

  getAll(limit = 50): Observable<ITrade[]> {
    return this.http.get<ITrade[]>('/api/trades', {
      params: { limit: String(limit) },
    });
  }
}
