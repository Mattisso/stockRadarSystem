---
title: "ATD Conventions"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, conventions]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# ATD Conventions

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

This document consolidates ATD-specific conventions referenced throughout the playbook. For detailed implementation guidance, see the linked documents.

## Project Structure

### Standard Folder Layout

ATD Angular projects follow Nx conventions with ATD-specific patterns:

```text
my-app/
├── apps/
│   └── my-app/
│       ├── src/
│       │   ├── app/
│       │   │   ├── app.component.ts
│       │   │   ├── app.config.ts
│       │   │   ├── app.routes.ts
│       │   │   └── features/
│       │   │       └── users/
│       │   │           ├── user-list-page/
│       │   │           │   ├── user-list-page.component.ts
│       │   │           │   ├── user-list-page.component.html
│       │   │           │   ├── user-list-page.component.scss
│       │   │           │   └── user-list-page.component.spec.ts
│       │   │           └── +state/
│       │   │               ├── users.actions.ts
│       │   │               ├── users.reducer.ts
│       │   │               ├── users.selectors.ts
│       │   │               └── users.effects.ts
│       │   ├── environments/
│       │   │   ├── environment.ts
│       │   │   ├── environment.dev.ts
│       │   │   ├── environment.xat.ts
│       │   │   └── environment.prod.ts
│       │   └── interceptors/
│       │       ├── auth.interceptor.ts
│       │       └── error.interceptor.ts
│       └── project.json
├── libs/
│   ├── ui-button/
│   ├── ui-modal/
│   └── user-api/
├── nx.json
└── package.json
```

### Key Conventions

| Item | Convention | Reference |
|------|------------|-----------|
| **Libraries** | Flat structure, no category folders | [[03-Nx-Workspace-Setup]] |
| **NgRx state** | `+state/` folder in feature directories | [[05-State-Management]] |
| **Environments** | local, dev, xat, prod | [[10-CI-CD-Integration]] |
| **Interceptors** | Dedicated `interceptors/` folder | [[06-API-Integration]] |

### Feature Organization

Features are organized by domain. Child components get their own subfolder within the page folder:

```text
features/
└── users/
    ├── user-list-page/                    # Page component folder
    │   ├── user-list-page.component.ts
    │   ├── user-list-page.component.html
    │   ├── user-list-page.component.scss
    │   ├── user-list-page.component.spec.ts
    │   ├── user-table/                    # Child component subfolder
    │   │   ├── user-table.component.ts
    │   │   ├── user-table.component.html
    │   │   ├── user-table.component.scss
    │   │   └── user-table.component.spec.ts
    │   └── user-filters/                  # Another child component
    │       ├── user-filters.component.ts
    │       ├── user-filters.component.html
    │       ├── user-filters.component.scss
    │       └── user-filters.component.spec.ts
    ├── user-detail-page/
    │   └── ...
    └── +state/                            # NgRx state for feature
        └── ...
```

**Do not create** generic `components/` subfolders - child components nest directly under their parent page.

---

## Naming Conventions

### Files and Folders

| Item | Convention | Example |
|------|------------|---------|
| Folders | kebab-case | `user-list-page/` |
| Component files | kebab-case + suffix | `user-card.component.ts` |
| Service files | kebab-case + suffix | `user-api.service.ts` |
| Model files | kebab-case | `user.model.ts` |
| Fixture files | kebab-case | `user.fixtures.ts` |
| Test files | kebab-case + `.spec` | `user-card.component.spec.ts` |
| NgRx files | kebab-case + type | `users.actions.ts`, `users.reducer.ts` |

### Components and Selectors

| Item | Convention | Example |
|------|------------|---------|
| Component class | PascalCase + `Component` | `UserCardComponent` |
| Page component class | PascalCase + `PageComponent` | `UserListPageComponent` |
| Selector | `atd-` prefix, kebab-case | `atd-user-card` |
| Page selector | `atd-` prefix + `-page` | `atd-user-list-page` |

```typescript
@Component({
  selector: 'atd-user-card',  // atd- prefix required
  // ...
})
export class UserCardComponent {}

@Component({
  selector: 'atd-user-list-page',  // atd- prefix + -page suffix
  // ...
})
export class UserListPageComponent {}
```

### Services

| Service Type | Naming | Example |
|--------------|--------|---------|
| **HTTP/API service** | `*ApiService` | `UserApiService`, `OrderApiService` |
| **Non-HTTP service** | `*Service` | `PermissionService`, `ValidationService`, `DateHelperService` |
| Store facade | `*Facade` | `UserFacade` |

**Naming rule:**
- `*ApiService` — Services that make HTTP calls (use `HttpClient`)
- `*Service` — All other services (utilities, helpers, business logic, etc.)

```typescript
// API service - wraps HTTP calls
@Injectable({ providedIn: 'root' })
export class UserApiService {
  private readonly http = inject(HttpClient);
  // Makes HTTP requests
}

// Non-HTTP services - no HTTP client
@Injectable({ providedIn: 'root' })
export class PermissionService {
  // Business logic, no HTTP
}

@Injectable({ providedIn: 'root' })
export class DateHelperService {
  // Utility functions, no HTTP
}
```

### NgRx Elements

| Element | Convention | Example |
|---------|------------|---------|
| Actions | `[Feature] Action Name` | `[Users] Load Users` |
| Action creators | camelCase | `loadUsers`, `loadUsersSuccess` |
| Reducer | `*Reducer` function | `usersReducer` |
| Selectors | `select*` prefix | `selectUsers`, `selectUserById` |
| Effects | `*Effects` class | `UsersEffects` |

```typescript
// Actions
export const UserActions = createActionGroup({
  source: 'Users',
  events: {
    'Load Users': emptyProps(),
    'Load Users Success': props<{ users: User[] }>(),
    'Load Users Failure': props<{ error: string }>()
  }
});

// Selectors
export const selectUsers = createSelector(
  selectUsersState,
  state => state.users
);
```

### Inputs and Outputs

| Item | Convention | Example |
|------|------------|---------|
| Signal inputs | camelCase | `user = input<User>()` |
| Required inputs | camelCase + `.required` | `userId = input.required<string>()` |
| Outputs | camelCase, event name (not past tense) | `click = output<void>()` |
| Output with data | camelCase, descriptive | `userSelected = output<User>()` |

```typescript
@Component({ /* ... */ })
export class UserCardComponent {
  // Inputs
  user = input.required<User>();
  showActions = input(true);

  // Outputs - use event names, not past tense
  selected = output<User>();      // Not "userSelected" or "onSelected"
  deleted = output<string>();     // Emits user ID
  actionClicked = output<void>(); // For simple events
}
```

### Variables and Functions

| Type | Convention | Example |
|------|------------|---------|
| Variables | camelCase | `userName`, `isLoading` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `API_BASE_URL` |
| Private fields | camelCase (no underscore) | `private readonly store` |
| Signals | camelCase, no `$` suffix | `users`, `loading` |
| Observables | camelCase with `$` suffix | `users$`, `loading$` |
| Enums | PascalCase | `UserStatus`, `OrderState` |

```typescript
// Enum naming
enum UserStatus {
  Active = 'ACTIVE',
  Inactive = 'INACTIVE',
  Pending = 'PENDING'
}

enum OrderState {
  Draft,
  Submitted,
  Approved,
  Rejected
}
```

---

## Code Style

### TypeScript Guidelines

**Required component configuration:**

```typescript
@Component({
  selector: 'atd-my-component',
  standalone: true,                              // Required
  changeDetection: ChangeDetectionStrategy.OnPush, // Required
  templateUrl: './my-component.component.html',  // External template
  styleUrl: './my-component.component.scss'      // External styles
})
export class MyComponent {
  // Use signal-based inputs for new components
  user = input.required<User>();
  showHeader = input(true);

  // Computed values from inputs
  displayName = computed(() => `${this.user().firstName} ${this.user().lastName}`);
}
```

**Dependency injection:**

```typescript
// Preferred: Field injection
export class MyComponent {
  private readonly store = inject(Store);
  private readonly router = inject(Router);
}

// Avoid: Constructor injection
export class MyComponent {
  constructor(private store: Store) {} // Don't do this
}
```

**Imports:**

```typescript
// Use tsconfig path aliases for cross-library imports
import { UserService } from '@atd/user-api';
import { ButtonComponent } from '@atd/ui-button';

// Don't use relative paths across libraries
import { UserService } from '../../../libs/user-api/src/lib/user.service'; // Wrong
```

### Template Guidelines

**Use modern control flow:**

```html
<!-- Preferred: Modern syntax -->
@if (loading()) {
  <atd-spinner />
} @else {
  <atd-user-list [users]="users()" />
}

@for (user of users(); track user.id) {
  <atd-user-card [user]="user" />
}

<!-- Avoid: Legacy directives in new code -->
<atd-spinner *ngIf="loading$ | async"></atd-spinner>
```

**No function calls in templates:**

```html
<!-- Wrong: Function executes every change detection -->
<span>{{ formatDate(user.createdAt) }}</span>

<!-- Correct: Use pipe or computed signal -->
<span>{{ user.createdAt | date:'shortDate' }}</span>
<span>{{ formattedDate() }}</span>
```

### Style Guidelines

**SCSS conventions:**

```scss
// Component styles are scoped automatically
:host {
  display: block;
}

// Use CSS custom properties for theming
.card {
  background: var(--card-background);
  border: 1px solid var(--border-color);
}

// Avoid deeply nested selectors (max 3 levels)
.card {
  .header {
    .title { /* OK */ }
  }
}
```

---

## Shared Libraries

### ATD Component Library

Shared UI components are organized as flat Nx libraries:

| Library | Purpose | Example Components |
|---------|---------|-------------------|
| `ui-button` | Button variants | Primary, Secondary, Icon buttons |
| `ui-modal` | Dialog/modal system | Confirmation, Form modals |
| `ui-data-table` | Data grid | Sortable, Paginated tables |
| `ui-form-controls` | Form elements | Inputs, Selects, Date pickers |

**Usage:**

```typescript
import { ButtonComponent } from '@atd/ui-button';
import { ModalService } from '@atd/ui-modal';

@Component({
  imports: [ButtonComponent]
})
export class MyComponent {
  private readonly modalService = inject(ModalService);
}
```

### Utility Libraries

| Library | Purpose |
|---------|---------|
| `util-date` | Date formatting, parsing |
| `util-validation` | Form validators |
| `util-testing` | Test utilities, fixtures |

### When to Create a Library

| Scenario | Action |
|----------|--------|
| Code used in 2+ places | Extract to library |
| Code shared across apps | Must be in library |
| Anticipate reuse | Can proactively extract |

**Use judgment and consult with leads when uncertain.** Library extraction is a design decision that can affect build times and dependency management. When in doubt about whether to extract code to a library, discuss with your team lead or architect.

See [[03-Nx-Workspace-Setup]] for library creation details.

### Barrel Files (index.ts)

ATD **discourages** barrel files (`index.ts`) except at library roots:

| Location | Barrel File | Reason |
|----------|-------------|--------|
| Library root (`libs/ui-button/src/index.ts`) | ✅ Allowed | Clean public API for library consumers |
| Feature folders | ❌ Avoid | Causes circular import issues |
| Component folders | ❌ Avoid | Unnecessary complexity |
| Nested directories | ❌ Avoid | Makes dependency tracking difficult |

```typescript
// GOOD: Library root barrel defines public API
// libs/ui-button/src/index.ts
export { ButtonComponent } from './lib/button.component';
export { ButtonVariant } from './lib/button.types';

// BAD: Barrel inside feature folder
// features/users/index.ts - Don't do this
export * from './user-list-page/user-list-page.component';
export * from './user-detail-page/user-detail-page.component';
```

Import directly from the source file when inside the same app or library.

---

## Authentication

### Okta Integration

ATD uses Okta for authentication in most applications:

```typescript
// app.config.ts
import { provideOktaAuth } from '@okta/okta-angular';
import { OktaAuth } from '@okta/okta-auth-js';

const oktaAuth = new OktaAuth({
  issuer: environment.authConfig.issuer,
  clientId: environment.authConfig.clientId,
  redirectUri: window.location.origin + '/callback',
  scopes: ['openid', 'profile', 'email']
});

export const appConfig: ApplicationConfig = {
  providers: [
    provideOktaAuth(oktaAuth)
  ]
};
```

### Auth Interceptor Pattern

```typescript
// interceptors/auth.interceptor.ts
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const oktaAuth = inject(OktaAuthService);

  // Skip auth for public endpoints
  if (req.url.includes('/public/')) {
    return next(req);
  }

  return from(oktaAuth.getAccessToken()).pipe(
    switchMap(token => {
      if (token) {
        const authReq = req.clone({
          setHeaders: { Authorization: `Bearer ${token}` }
        });
        return next(authReq);
      }
      return next(req);
    })
  );
};
```

### Route Guards

Angular 20 prefers functional guards. ATD uses functional guards for custom logic:

```typescript
// guards/auth.guard.ts
export const authGuard: CanActivateFn = (route, state) => {
  const oktaAuth = inject(OktaAuthService);
  const router = inject(Router);

  return oktaAuth.isAuthenticated$.pipe(
    map(isAuthenticated => {
      if (!isAuthenticated) {
        router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
        return false;
      }
      return true;
    })
  );
};

// app.routes.ts
export const routes: Routes = [
  {
    path: 'dashboard',
    component: DashboardPageComponent,
    canActivate: [authGuard]
  }
];
```

**Okta's class-based guard:** The `@okta/okta-angular` library provides `OktaAuthGuard` as a class-based guard. This is acceptable when using Okta's built-in guard:

```typescript
import { OktaAuthGuard } from '@okta/okta-angular';

export const routes: Routes = [
  {
    path: 'protected',
    component: ProtectedPageComponent,
    canActivate: [OktaAuthGuard]  // Okta's class-based guard is acceptable
  },
  {
    path: 'callback',
    component: OktaCallbackComponent
  }
];
```

> **Note:** Some ATD applications use custom authentication. Adapt patterns accordingly.

---

## Browser API Injection Tokens

ATD uses injection tokens to abstract browser globals, improving testability:

```typescript
// tokens/window.token.ts
import { InjectionToken } from '@angular/core';

export const WINDOW = new InjectionToken<Window>('window', {
  factory: () => window
});

export const DOCUMENT = new InjectionToken<Document>('document', {
  factory: () => document
});

// Usage - inject instead of using globals directly
@Injectable({ providedIn: 'root' })
export class NavigationService {
  private readonly window = inject(WINDOW);

  navigateTo(url: string): void {
    this.window.location.href = url;
  }
}
```

This pattern allows mocking browser APIs in tests without global state pollution.

---

## Error Handling

### Standard Error Patterns

ATD uses a centralized approach to error handling:

**Global error interceptor:**

```typescript
// interceptors/error.interceptor.ts
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const window = inject(WINDOW);
  const env = inject(ENVIRONMENT);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401) {
        // Redirect to login
        window.location.href = '/login';
      } else if (error.status >= 500) {
        // Redirect to centralized error page
        window.location.href = `${env.errorAppUrl}?code=${error.status}`;
      }
      return throwError(() => error);
    })
  );
};
```

**Centralized error application:**

ATD has a separate error application that displays user-friendly messages:

```text
API Error (500) → Error Interceptor → Redirect to error app → User sees friendly message
```

### User Messaging

| Error Type | Handling |
|------------|----------|
| Validation errors | Display inline in form |
| Business errors | Display in toast/notification |
| Server errors (5xx) | Redirect to error app |
| Auth errors (401) | Redirect to login |
| Not found (404) | Display contextual message |

---

## Logging Standards

### What to Log

| Level | When to Use | Examples |
|-------|-------------|----------|
| **ERROR** | Unexpected failures | Unhandled exceptions, API failures |
| **WARN** | Recoverable issues | Fallback used, deprecated feature |
| **INFO** | Key events | User actions, navigation, feature flags |
| **DEBUG** | Development details | State changes, API payloads (dev only) |

### What NOT to Log

- Sensitive data (passwords, tokens, PII)
- Full API responses in production
- Excessive noise (every keystroke, mouse movement)

### Logging Pattern

```typescript
@Injectable({ providedIn: 'root' })
export class LoggingService {
  private readonly isProduction = inject(ENVIRONMENT).production;

  error(message: string, context?: unknown): void {
    console.error(`[ERROR] ${message}`, context);
    // In production: send to logging service
  }

  warn(message: string, context?: unknown): void {
    console.warn(`[WARN] ${message}`, context);
  }

  info(message: string, context?: unknown): void {
    if (!this.isProduction) {
      console.info(`[INFO] ${message}`, context);
    }
  }

  debug(message: string, context?: unknown): void {
    if (!this.isProduction) {
      console.debug(`[DEBUG] ${message}`, context);
    }
  }
}
```

---

## Environment Configuration

### Standard Environments

| Environment | File | Purpose |
|-------------|------|---------|
| `local` | `environment.ts` | Local development |
| `dev` | `environment.dev.ts` | Development server |
| `xat` | `environment.xat.ts` | UAT/Performance testing |
| `prod` | `environment.prod.ts` | Production |

### Environment Type Interface

Define a shared interface to ensure all environments have the same shape:

```typescript
// environment.interface.ts
export interface Environment {
  production: boolean;
  apiUrl: string;
  authConfig: {
    issuer: string;
    clientId: string;
  };
  errorAppUrl: string;
  featureFlags: {
    newDashboard: boolean;
    betaFeatures: boolean;
  };
}
```

### Environment Injection Token

ATD uses an injection token to provide the environment, enabling testability:

```typescript
// tokens/environment.token.ts
import { InjectionToken } from '@angular/core';
import { Environment } from './environment.interface';

export const ENVIRONMENT = new InjectionToken<Environment>('environment');

// app.config.ts
import { environment } from '../environments/environment';

export const appConfig: ApplicationConfig = {
  providers: [
    { provide: ENVIRONMENT, useValue: environment }
  ]
};

// Usage in services
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly env = inject(ENVIRONMENT);

  get apiUrl(): string {
    return this.env.apiUrl;
  }
}
```

### Environment File Structure

```typescript
// environment.ts (local development)
import { Environment } from './environment.interface';

export const environment: Environment = {
  production: false,
  apiUrl: '/api',  // Proxied to dev backend
  authConfig: {
    issuer: 'https://atd-dev.okta.com/oauth2/default',
    clientId: 'local-client-id'
  },
  errorAppUrl: 'https://error.dev.atd.com',
  featureFlags: {
    newDashboard: true,
    betaFeatures: true
  }
};
```

```typescript
// environment.prod.ts
import { Environment } from './environment.interface';

export const environment: Environment = {
  production: true,
  apiUrl: 'https://api.atd.com',
  authConfig: {
    issuer: 'https://atd.okta.com/oauth2/default',
    clientId: 'prod-client-id'
  },
  errorAppUrl: 'https://error.atd.com',
  featureFlags: {
    newDashboard: true,
    betaFeatures: false
  }
};
```

---

## Quick Reference

### Component Checklist

- [ ] Selector uses `atd-` prefix
- [ ] `standalone: true`
- [ ] `changeDetection: OnPush`
- [ ] All 4 files present (`.component.ts`, `.component.html`, `.component.scss`, `.component.spec.ts`)
- [ ] Uses `inject()` for dependencies
- [ ] Uses signal-based inputs for new components

### Service Checklist

- [ ] HTTP services named `*ApiService`, non-HTTP services named `*Service`
- [ ] Returns `Observable<T>` (no subscriptions)
- [ ] No Store injection (effects handle that)
- [ ] Transforms API responses to domain models

### NgRx Checklist

- [ ] State in `+state/` folder
- [ ] Actions use `[Feature] Name` format
- [ ] Selectors prefixed with `select`
- [ ] Effects use services, not direct HTTP

---

## Related Documents

- [[01-Getting-Started]] - Initial setup conventions
- [[03-Nx-Workspace-Setup]] - Project structure details
- [[04-Component-Architecture]] - Component patterns
- [[05-State-Management]] - NgRx conventions
- [[06-API-Integration]] - API and service patterns

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.3 | Clarified service naming rule (*ApiService for HTTP, *Service for non-HTTP); added "consult leads" guidance for library extraction decisions |
| 2026-01-21 | 1.2 | Added signal inputs/outputs, enum naming, functional guards, environment interface/tokens, browser API tokens, barrel file guidance |
| 2026-01-19 | 1.1 | Full content added: naming, structure, auth, error handling |
| 2026-01-08 | 1.0 | Initial stub created |
