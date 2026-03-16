import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ISignal } from '../../shared/models';

@Injectable({ providedIn: 'root' })
export class SignalsApiService {
  private readonly http = inject(HttpClient);

  getAll(limit = 50): Observable<ISignal[]> {
    return this.http.get<ISignal[]>('/api/signals', {
      params: { limit: String(limit) },
    });
  }
}
