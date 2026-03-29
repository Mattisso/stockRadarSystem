import { Injectable, OnDestroy, inject } from '@angular/core';
import { Observable, Subject, timer } from 'rxjs';
import { filter, map, retryWhen, switchMap, tap } from 'rxjs/operators';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { AuthService } from './auth.service';
import { runtimeConfig } from './runtime-config';

export interface WsMessage<T = unknown> {
  topic: string;
  data: T;
}

type WsPath = '/ws' | '/ws/l1' | '/ws/l2' | '/ws/signals' | '/ws/trades';

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly sockets = new Map<WsPath, WebSocketSubject<WsMessage>>();
  private readonly channelMessages = new Map<WsPath, Subject<WsMessage>>();
  private readonly retryAttempts = new Map<WsPath, number>();

  topic$<T>(topic: string): Observable<T> {
    return this.channelTopic$('/ws', topic);
  }

  channelTopic$<T>(path: WsPath, topic: string): Observable<T> {
    const channel$ = this.ensureChannel(path);
    return channel$.pipe(
      filter(msg => msg.topic === topic),
      map(msg => msg.data as T),
    );
  }

  private ensureChannel(path: WsPath): Subject<WsMessage> {
    const existing = this.channelMessages.get(path);
    if (existing) {
      return existing;
    }

    const messages$ = new Subject<WsMessage>();
    this.channelMessages.set(path, messages$);

    const socket$ = webSocket<WsMessage>({
      url: this.wsUrl(path),
      openObserver: {
        next: () => {
          this.retryAttempts.set(path, 0);
        },
      },
    });
    this.sockets.set(path, socket$);

    socket$
      .pipe(
        retryWhen(errors =>
          errors.pipe(
            tap(() => this.retryAttempts.set(path, (this.retryAttempts.get(path) ?? 0) + 1)),
            switchMap(() => {
              const retryAttempt = this.retryAttempts.get(path) ?? 0;
              const delay = Math.min(1000 * Math.pow(2, retryAttempt), 30000);
              return timer(delay);
            }),
          ),
        ),
      )
      .subscribe({
        next: msg => messages$.next(msg),
        error: () => {},
      });

    return messages$;
  }

  private wsUrl(path: WsPath): string {
    const token = this.auth.token;
    return `${runtimeConfig.wsBaseUrl}${path}?token=${token}`;
  }

  ngOnDestroy(): void {
    for (const socket of this.sockets.values()) {
      socket.complete();
    }
    for (const channel$ of this.channelMessages.values()) {
      channel$.complete();
    }
  }
}
