import { Injectable, signal } from '@angular/core';

export interface ApiMetadata {
  url: string;
  method: string;
  curl: string;
  tables: string[];
  responseTimeMs: string;
  timestamp: Date;
}

@Injectable({
  providedIn: 'root'
})
export class DebugStorageService {
  private lastRequestSignal = signal<ApiMetadata | null>(null);
  
  readonly lastRequest = this.lastRequestSignal.asReadonly();

  setLastRequest(metadata: ApiMetadata) {
    this.lastRequestSignal.set(metadata);
  }

  clear() {
    this.lastRequestSignal.set(null);
  }
}
