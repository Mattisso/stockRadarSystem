---
title: "API Integration"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, api, http, interceptors, okta]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# API Integration

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## HttpClient Setup

### Providing HttpClient

Configure HttpClient in your application config with functional interceptors:

```typescript
// app.config.ts
import { ApplicationConfig } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './interceptors/auth.interceptor';
import { errorInterceptor } from './interceptors/error.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(
      withInterceptors([
        authInterceptor,
        errorInterceptor
      ])
    )
  ]
};
```

### Interceptor Order

Interceptors execute in the order provided. ATD's typical stack:

1. **Auth interceptor** - Adds authorization token
2. **Error interceptor** - Handles HTTP errors globally

### Future: Fetch Backend

ATD currently uses the default XMLHttpRequest backend. Angular's `withFetch()` option provides the modern Fetch API:

```typescript
// Future consideration
provideHttpClient(
  withFetch(),
  withInterceptors([...])
)
```

Benefits of `withFetch()`:

- Native streaming support
- Better integration with service workers
- Modern browser features

This may be adopted in future ATD projects as browser support and Angular tooling mature.

---

## Service Patterns

### Naming Convention

**API services must include "API" in their name** to distinguish them from utility services:

| Service Type | Naming | Example |
|--------------|--------|---------|
| API service (wraps backend) | Include "API" | `UserApiService`, `ProductApiService` |
| Utility service (no backend) | No "API" | `DateHelperService`, `ValidationService` |

### RESTful Service Design

One service per API domain with methods mirroring REST verbs:

```typescript
// user-api.service.ts
@Injectable({ providedIn: 'root' })
export class UserApiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api/users';

  getAll(): Observable<User[]> {
    return this.http.get<UserApiResponse[]>(this.apiUrl).pipe(
      map(response => this.mapToUsers(response))
    );
  }

  getById(id: string): Observable<User> {
    return this.http.get<UserApiResponse>(`${this.apiUrl}/${id}`).pipe(
      map(response => this.mapToUser(response))
    );
  }

  create(user: UserCreateRequest): Observable<User> {
    return this.http.post<UserApiResponse>(this.apiUrl, user).pipe(
      map(response => this.mapToUser(response))
    );
  }

  update(id: string, user: UserUpdateRequest): Observable<User> {
    return this.http.put<UserApiResponse>(`${this.apiUrl}/${id}`, user).pipe(
      map(response => this.mapToUser(response))
    );
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  // Transform API response to domain model
  private mapToUser(response: UserApiResponse): User {
    return {
      id: response.user_id,
      name: `${response.first_name} ${response.last_name}`,
      email: response.email_address,
      active: response.is_active === 'Y'
    };
  }

  private mapToUsers(response: UserApiResponse[]): User[] {
    return response.map(r => this.mapToUser(r));
  }
}
```

### Key Principles

| Principle | Description |
|-----------|-------------|
| **Return Observables** | Always return `Observable<T>` - let effects handle subscription |
| **No Store access** | Services should NOT inject Store or dispatch actions |
| **Transform in service** | Map API responses to domain models before returning |
| **Single responsibility** | One API domain per service |

---

## Type Safety and DTOs

### Separate API Types from Domain Models

API responses are often messy (inconsistent casing, extra fields, different structures). Define separate interfaces:

```typescript
// api-types/user-api.types.ts
// Matches the actual API response structure
export interface UserApiResponse {
  user_id: string;
  first_name: string;
  last_name: string;
  email_address: string;
  is_active: 'Y' | 'N';
  created_dt: string;
  modified_dt: string;
  department_cd: string;
  // ... other API-specific fields
}

export interface UserCreateRequest {
  first_name: string;
  last_name: string;
  email_address: string;
  department_cd: string;
}
```

```typescript
// models/user.model.ts
// Clean domain model used throughout the application
export interface User {
  id: string;
  name: string;
  email: string;
  active: boolean;
  department?: string;
}
```

### Transformation Flow

```text
API Response (UserApiResponse)
    ↓
Service transforms
    ↓
Domain Model (User)
    ↓
Effect receives clean data
    ↓
Store/Components use domain model
```

This separation:

- Isolates API changes from application code
- Provides clean, consistent types throughout the app
- Makes testing easier with predictable domain models

---

## Interceptors

### Authentication Interceptor

ATD uses Okta for authentication. The auth interceptor adds the bearer token:

```typescript
// interceptors/auth.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { OktaAuthService } from '@okta/okta-angular';
import { from, switchMap } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const oktaAuth = inject(OktaAuthService);

  // Skip auth for public endpoints if needed
  if (req.url.includes('/public/')) {
    return next(req);
  }

  return from(oktaAuth.getAccessToken()).pipe(
    switchMap(token => {
      if (token) {
        const authReq = req.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`
          }
        });
        return next(authReq);
      }
      return next(req);
    })
  );
};
```

> **Note:** Some ATD applications use custom authentication instead of Okta. Adapt the interceptor pattern accordingly.

### Error Interceptor

The error interceptor handles HTTP errors before they reach effects:

```typescript
// interceptors/error.interceptor.ts
import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { OktaAuthService } from '@okta/okta-angular';
import { LoggingService } from '../services/logging.service';
import { catchError, throwError } from 'rxjs';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const oktaAuth = inject(OktaAuthService);
  const logger = inject(LoggingService);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      switch (error.status) {
        case 401:
          // Unauthorized - trigger Okta login flow
          oktaAuth.signInWithRedirect();
          break;
        case 403:
          // Forbidden - user lacks permission
          // Let effect handle navigation to forbidden page
          break;
        case 0:
          // Network error - no response received
          logger.error('Network error', { url: req.url, error });
          break;
        // Other status codes fall through to re-throw
      }

      // Re-throw so effects can handle specific cases
      return throwError(() => error);
    })
  );
};
```

> **Note:** For applications using custom authentication instead of Okta, replace `oktaAuth.signInWithRedirect()` with appropriate redirect logic.

### Logging Interceptor (Optional)

For debugging API calls during development, a logging interceptor can be helpful:

```typescript
// interceptors/logging.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap, finalize } from 'rxjs';
import { LoggingService } from '../services/logging.service';

export const loggingInterceptor: HttpInterceptorFn = (req, next) => {
  const logger = inject(LoggingService);
  const startTime = Date.now();

  logger.debug(`HTTP ${req.method} ${req.url}`);

  return next(req).pipe(
    tap({
      next: (event) => {
        if (event.type !== 0) { // Skip initial event
          logger.debug(`HTTP ${req.method} ${req.url} completed`, {
            duration: Date.now() - startTime
          });
        }
      },
      error: (error) => {
        logger.warn(`HTTP ${req.method} ${req.url} failed`, {
          duration: Date.now() - startTime,
          status: error.status
        });
      }
    })
  );
};
```

Add to your interceptor stack in development only:

```typescript
provideHttpClient(
  withInterceptors([
    authInterceptor,
    ...(isDevMode() ? [loggingInterceptor] : []),
    errorInterceptor
  ])
)
```

### Error Application Integration

ATD has a centralized error application that displays user-friendly error messages. The flow:

1. Effect catches error after retry attempts
2. If unrecoverable, application redirects to error app
3. Error app displays cleansed, user-friendly message

This keeps error presentation consistent across ATD applications.

---

## Error Handling in Effects

Effects should handle errors after the interceptor has done initial processing:

```typescript
// user.effects.ts
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userApiService.getAll().pipe(
        map(users => UserActions.usersLoaded({ users })),
        catchError(error => of(UserActions.usersLoadFailed({
          error: this.getErrorMessage(error)
        })))
      )
    )
  )
);

private getErrorMessage(error: HttpErrorResponse): string {
  if (error.status === 0) {
    return 'Unable to connect to server';
  }
  if (error.status >= 500) {
    return 'Server error. Please try again later.';
  }
  return error.message || 'An unexpected error occurred';
}
```

### Retry Logic

For transient failures, add retry logic:

```typescript
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userApiService.getAll().pipe(
        retry({ count: 3, delay: 1000 }),
        map(users => UserActions.usersLoaded({ users })),
        catchError(error => of(UserActions.usersLoadFailed({
          error: this.getErrorMessage(error)
        })))
      )
    )
  )
);
```

---

## RxJS Flattening Operators

Choosing the right flattening operator is critical for correct behavior in effects. Each operator handles concurrent inner observables differently.

### Operator Comparison

| Operator | Behavior | Use When |
|----------|----------|----------|
| `switchMap` | Cancels previous, runs latest only | User typing search, navigation, latest-wins scenarios |
| `mergeMap` | Runs all concurrently | Independent operations, batch processing, no cancellation needed |
| `concatMap` | Queues in order, waits for each | Order matters, sequential operations, form submissions |
| `exhaustMap` | Ignores new until current completes | Prevent double-submit, login buttons, single-flight requests |

### switchMap - Cancel Previous

**Use for:** Search-as-you-type, navigation, any "latest wins" scenario.

```typescript
// User types: "a" -> "ab" -> "abc"
// Only the "abc" request completes; "a" and "ab" are cancelled
searchUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.search),
    switchMap(({ term }) =>
      this.userApiService.search(term).pipe(
        map(users => UserActions.searchSuccess({ users })),
        catchError(error => of(UserActions.searchFailed({ error: error.message })))
      )
    )
  )
);
```

**Warning:** Don't use `switchMap` for operations that must complete (saves, deletes). A rapid second click would cancel the first save.

### mergeMap - Run All Concurrently

**Use for:** Independent operations where all must complete, batch processing.

```typescript
// Delete multiple users - all requests run in parallel
deleteUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.deleteMultiple),
    mergeMap(({ userIds }) =>
      from(userIds).pipe(
        mergeMap(id =>
          this.userApiService.delete(id).pipe(
            map(() => UserActions.userDeleted({ id })),
            catchError(error => of(UserActions.deleteFailed({ id, error: error.message })))
          )
        )
      )
    )
  )
);
```

**Warning:** Uncontrolled concurrency can overwhelm the server. Use `mergeMap(fn, concurrency)` to limit:

```typescript
mergeMap(id => this.userApiService.delete(id), 3) // Max 3 concurrent
```

### concatMap - Sequential Queue

**Use for:** Operations where order matters, sequential processing, form submissions where you need confirmation before allowing another.

```typescript
// Process items in order - each waits for the previous to complete
processQueue$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.processNext),
    concatMap(({ item }) =>
      this.userApiService.process(item).pipe(
        map(result => UserActions.processSuccess({ result })),
        catchError(error => of(UserActions.processFailed({ error: error.message })))
      )
    )
  )
);
```

**Warning:** If requests are slow and actions arrive quickly, the queue grows unbounded. Consider `exhaustMap` if you want to ignore requests while one is in flight.

### exhaustMap - Ignore Until Complete

**Use for:** Preventing double-submit, login/logout buttons, any operation that should only run once at a time.

```typescript
// Submit button - ignore clicks while request is in flight
submitForm$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.submitForm),
    exhaustMap(({ formData }) =>
      this.userApiService.submit(formData).pipe(
        map(result => UserActions.submitSuccess({ result })),
        catchError(error => of(UserActions.submitFailed({ error: error.message })))
      )
    )
  )
);
```

This is often better than disabling the button in the UI because it handles rapid clicks that might occur before the UI updates.

### Decision Guide

```text
Is the operation cancellable?
├── Yes: Do you want the latest result only?
│   ├── Yes → switchMap (search, navigation)
│   └── No → mergeMap (batch operations)
└── No: Should new requests wait or be ignored?
    ├── Wait (queue) → concatMap (ordered processing)
    └── Ignore → exhaustMap (prevent double-submit)
```

### Common Mistakes

```typescript
// WRONG: Using switchMap for save operations
saveUser$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.saveUser),
    switchMap(({ user }) => // Rapid clicks cancel previous saves!
      this.userApiService.save(user).pipe(...)
    )
  )
);

// CORRECT: Use exhaustMap to ignore while saving
saveUser$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.saveUser),
    exhaustMap(({ user }) => // Ignores clicks while save is in progress
      this.userApiService.save(user).pipe(...)
    )
  )
);
```

---

## Local Development Setup

### Proxy Configuration

ATD uses proxy configuration exclusively for local development. This routes API calls to the development backend:

```json
// proxy.conf.json
{
  "/api/*": {
    "target": "https://dev-api.atd.com",
    "secure": true,
    "changeOrigin": true,
    "logLevel": "debug"
  }
}
```

Configure in `project.json`:

```json
{
  "targets": {
    "serve": {
      "options": {
        "proxyConfig": "proxy.conf.json"
      }
    }
  }
}
```

### Why Proxy Over Environment URLs

| Approach | ATD Usage | Reason |
|----------|-----------|--------|
| Proxy config | **Standard** | Avoids CORS, simpler configuration |
| Environment base URLs | Rare | Only when proxy doesn't work |

Services use relative URLs (`/api/users`) rather than absolute URLs. The proxy handles routing.

---

## Caching

### NgRx as the Cache Layer

ATD does not typically implement caching at the service level. The NgRx store serves as the application cache:

| Approach | ATD Usage | Reason |
|----------|-----------|--------|
| Service-level caching | **Avoid** | Duplicates NgRx responsibility |
| `shareReplay()` | **Avoid** | NgRx handles this |
| NgRx store | **Standard** | Single source of truth |

### Pattern: Check Store Before Fetching

```typescript
// In selector file - track if data has been loaded
export const selectUsersLoaded = createSelector(
  selectUsersState,
  state => state.users.length > 0 || state.loadedAt !== null
);

// In effect - skip fetch if data exists
loadUsersIfNeeded$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsersIfNeeded),
    concatLatestFrom(() => this.store.select(selectUsersLoaded)),
    filter(([, loaded]) => !loaded),
    map(() => UserActions.loadUsers())
  )
);
```

---

## Pagination

Many APIs return paginated data. Handle pagination in NgRx state:

### State Shape

```typescript
export interface UsersState {
  users: User[];
  pagination: {
    currentPage: number;
    pageSize: number;
    totalItems: number;
    totalPages: number;
  };
  loading: boolean;
  error: string | null;
}
```

### Service Pattern

```typescript
@Injectable({ providedIn: 'root' })
export class UserApiService {
  private readonly http = inject(HttpClient);

  getPage(page: number, pageSize: number): Observable<PaginatedResponse<User>> {
    return this.http.get<PaginatedApiResponse>('/api/users', {
      params: { page: page.toString(), size: pageSize.toString() }
    }).pipe(
      map(response => ({
        items: response.data.map(u => this.mapToUser(u)),
        pagination: {
          currentPage: response.page,
          pageSize: response.size,
          totalItems: response.total_count,
          totalPages: response.total_pages
        }
      }))
    );
  }
}
```

### Effect Pattern

```typescript
loadUsersPage$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadPage),
    switchMap(({ page, pageSize }) =>
      this.userApiService.getPage(page, pageSize).pipe(
        map(response => UserActions.pageLoaded(response)),
        catchError(error => of(UserActions.loadFailed({ error: error.message })))
      )
    )
  )
);
```

---

## API Versioning

ATD does not have formalized API versioning standards. Most APIs are custom to their application and are updated in lockstep with the frontend.

When versioning is needed:

| Approach | Usage |
|----------|-------|
| URL path versioning | `/api/v1/users` - most common when used |
| Header versioning | `X-API-Version: 1` - less common |

Since frontends and backends typically deploy together, breaking API changes are coordinated during development.

---

## Anti-Patterns to Avoid

### Services Dispatching Actions

Services should return Observables—they should never inject Store or dispatch actions. See [[05-State-Management#Services Dispatching Actions]] for the full pattern.

### Subscribing in Services

```typescript
// WRONG: Subscribing in service
getUser(id: string): User {
  let user: User;
  this.http.get<User>(`/api/users/${id}`).subscribe(u => user = u);
  return user; // Returns undefined!
}

// CORRECT: Return Observable
getUser(id: string): Observable<User> {
  return this.http.get<UserApiResponse>(`/api/users/${id}`).pipe(
    map(response => this.mapToUser(response))
  );
}
```

### Using Base URLs in Environment Files

```typescript
// WRONG: Absolute URLs with environment config
@Injectable({ providedIn: 'root' })
export class UserApiService {
  private readonly apiUrl = environment.apiBaseUrl + '/users';
}

// CORRECT: Relative URLs with proxy
@Injectable({ providedIn: 'root' })
export class UserApiService {
  private readonly apiUrl = '/api/users';
}
```

---

## Related Documents

- [[05-State-Management]] - Effects and error actions
- [[07-Testing-Strategies]] - Mocking HTTP calls
- [[12-ATD-Conventions]] - Service naming conventions

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Added comprehensive RxJS flattening operators guide; added logging interceptor; added pagination patterns; fixed error interceptor for Okta flow; replaced duplicate anti-pattern with reference |
| 2026-01-14 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
