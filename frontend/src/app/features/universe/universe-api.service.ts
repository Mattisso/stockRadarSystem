import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ISymbol } from '../../shared/models';

@Injectable({ providedIn: 'root' })
export class UniverseApiService {
  private readonly http = inject(HttpClient);

  getAll(activeOnly = true): Observable<ISymbol[]> {
    return this.http.get<ISymbol[]>('/api/universe', {
      params: { active_only: String(activeOnly) },
    });
  }
}
