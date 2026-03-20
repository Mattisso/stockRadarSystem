import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { IStateMachineEntry } from '../../shared/models/state-machine.model';

@Injectable({ providedIn: 'root' })
export class StateMonitorApiService {
  private readonly http = inject(HttpClient);

  getAll(): Observable<IStateMachineEntry[]> {
    return this.http.get<IStateMachineEntry[]>('/api/state-machine');
  }
}
