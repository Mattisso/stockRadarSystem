import { Injectable, OnDestroy, inject } from '@angular/core';
import { Observable, Subject, timer, EMPTY } from 'rxjs';
import { filter, map, retryWhen, switchMap, tap } from 'rxjs/operators';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { AuthService } from './auth.service';

export interface WsMessage<T = unknown> {
  topic: string;
  data: T;
}

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private readonly auth = inject(AuthService);
  private socket$: WebSocketSubject<WsMessage> | null = null;
  private readonly messages$ = new Subject<WsMessage>();
  private readonly destroy$ = new Subject<void>();
  private retryAttempt = 0;

  constructor() {
    this.connect();
  }

  private get wsUrl(): string {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = this.auth.token;
    return `${proto}//${location.host}/api/ws?token=${token}`;
  }

  private connect(): void {
    this.socket$ = webSocket<WsMessage>({
      url: this.wsUrl,
      openObserver: {
        next: () => {
          this.retryAttempt = 0;
        },
      },
    });

    this.socket$
      .pipe(
        retryWhen(errors =>
          errors.pipe(
            tap(() => this.retryAttempt++),
            switchMap(() => {
              const delay = Math.min(1000 * Math.pow(2, this.retryAttempt), 30000);
              return timer(delay);
            }),
          ),
        ),
      )
      .subscribe({
        next: msg => this.messages$.next(msg),
        error: () => {},
      });
  }

  topic$<T>(topic: string): Observable<T> {
    return this.messages$.pipe(
      filter(msg => msg.topic === topic),
      map(msg => msg.data as T),
    );
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.socket$?.complete();
  }
}
