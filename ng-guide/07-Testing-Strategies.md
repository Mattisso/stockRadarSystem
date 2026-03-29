---
title: "Testing Strategies"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, testing, jest, vitest, ngrx, fixtures]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# Testing Strategies

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## Testing Philosophy at ATD

### Test Pyramid

ATD follows the standard test pyramid with strong emphasis on unit testing:

| Level | Coverage Goal | Purpose |
|-------|---------------|---------|
| **Unit tests** | 90%+ | Core testing layer, fast feedback |
| **Integration tests** | Complex code paths | Test component interactions |
| **E2E tests** | Critical journeys | Currently external, moving toward in-repo |

### Overall Coverage Requirements

| Area | Target | Enforcement |
|------|--------|-------------|
| Overall unit coverage | **90%+** | CI gate |
| NgRx (reducers, effects, selectors) | **100%** | Critical path |
| Component public methods | **100%** | Required |
| API services | **100%** | Include error cases |

NgRx code requires nearly 100% coverage because it represents the most critical parts of the application. Any issues there need to be caught immediately.

---

## Unit Testing

ATD currently uses **Jest** as the test runner (Nx default). The migration to **Vitest** will occur with the **Angular 21 upgrade** (planned for 2026). Until then, continue using Jest for all testing. The patterns below work with both runners.

### Basic Test Structure

```typescript
// user.service.spec.ts
import { TestBed } from '@angular/core/testing';
import { UserApiService } from './user-api.service';

describe('UserApiService', () => {
  let service: UserApiService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [UserApiService]
    });
    service = TestBed.inject(UserApiService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('getAll', () => {
    it('should return users on success', () => {
      // Arrange, Act, Assert
    });

    it('should handle 500 errors', () => {
      // Always test error cases
    });
  });
});
```

### AAA Pattern

Follow Arrange-Act-Assert for clear test structure:

```typescript
it('should transform API response to domain model', () => {
  // Arrange
  const apiResponse = createUserApiResponse({ user_id: '123', first_name: 'John' });

  // Act
  const result = service.mapToUser(apiResponse);

  // Assert
  expect(result.id).toBe('123');
  expect(result.name).toContain('John');
});
```

---

## Component Testing

### Coverage Requirements

| What to Test | Coverage |
|--------------|----------|
| Public methods | **100%** |
| Input/Output behavior (signal or decorator) | **100%** |
| Template rendering | Limited (special cases only) |

### Testing Public Methods

All public component methods must be tested:

```typescript
// user-list-page.component.spec.ts
describe('UserListPageComponent', () => {
  let component: UserListPageComponent;
  let fixture: ComponentFixture<UserListPageComponent>;
  let store: MockStore;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserListPageComponent],
      providers: [provideMockStore({ initialState: {} })]
    }).compileComponents();

    fixture = TestBed.createComponent(UserListPageComponent);
    component = fixture.componentInstance;
    store = TestBed.inject(MockStore);
  });

  describe('onFiltersChanged', () => {
    it('should dispatch setFilters action', () => {
      const dispatchSpy = jest.spyOn(store, 'dispatch');
      const filters = createUserFilters({ status: 'active' });

      component.onFiltersChanged(filters);

      expect(dispatchSpy).toHaveBeenCalledWith(
        UserActions.setFilters({ filters })
      );
    });
  });

  describe('onUserSelected', () => {
    it('should dispatch selectUser action', () => {
      const dispatchSpy = jest.spyOn(store, 'dispatch');
      const user = createUser({ id: '123' });

      component.onUserSelected(user);

      expect(dispatchSpy).toHaveBeenCalledWith(
        UserActions.selectUser({ user })
      );
    });
  });
});
```

### Testing Private Methods

When private methods contain significant logic, make them testable:

```typescript
// Preferred: Extract to a helper service
@Injectable()
export class UserHelperService {
  calculateDisplayName(user: User): string {
    // Complex logic now publicly testable
  }
}
```

When extraction isn't practical, access the private method with an ESLint ignore comment:

```typescript
it('should calculate display name correctly', () => {
  // eslint-disable-next-line @typescript-eslint/dot-notation
  const result = component['calculateDisplayName'](user);
  expect(result).toBe('Expected Name');
});
```

**Strongly prefer extraction.** Direct private access is a test smell indicating the method may belong in a service.

### Template Testing (Limited)

Template tests are added only for critical UI behavior:

```typescript
import { By } from '@angular/platform-browser';

// Only when template behavior is critical
it('should display error message when loading fails', () => {
  store.setState({ users: { error: 'Failed to load', loading: false } });
  fixture.detectChanges();

  const errorElement = fixture.debugElement.query(By.css('.error-message'));
  expect(errorElement.nativeElement.textContent).toContain('Failed to load');
});
```

### Testing Signal-Based Components

For components using signal inputs, set values via `ComponentRef.setInput()`:

```typescript
describe('UserCardComponent (signal inputs)', () => {
  let component: UserCardComponent;
  let fixture: ComponentFixture<UserCardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserCardComponent]
    }).compileComponents();

    fixture = TestBed.createComponent(UserCardComponent);
    component = fixture.componentInstance;
  });

  it('should accept user via signal input', () => {
    const user = createUser({ id: '123', name: 'Test User' });

    // Set signal input value
    fixture.componentRef.setInput('user', user);
    fixture.detectChanges();

    expect(component.user()).toEqual(user);
  });

  it('should emit via signal output', () => {
    const user = createUser({ id: '123' });
    fixture.componentRef.setInput('user', user);

    // Subscribe to output
    const selectedSpy = jest.fn();
    component.selected.subscribe(selectedSpy);

    component.onSelect();

    expect(selectedSpy).toHaveBeenCalledWith(user);
  });
});
```

### Testing Components with selectSignal

```typescript
describe('UserListPageComponent', () => {
  let component: UserListPageComponent;
  let fixture: ComponentFixture<UserListPageComponent>;
  let store: MockStore;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserListPageComponent],
      providers: [
        provideMockStore({
          selectors: [
            { selector: selectAllUsers, value: [] },
            { selector: selectUsersLoading, value: false }
          ]
        })
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(UserListPageComponent);
    component = fixture.componentInstance;
    store = TestBed.inject(MockStore);
  });

  it('should reflect store state via selectSignal', () => {
    const users = [createUser({ id: '1' }), createUser({ id: '2' })];

    store.overrideSelector(selectAllUsers, users);
    store.refreshState();
    fixture.detectChanges();

    // Signal returns current value
    expect(component.users()).toEqual(users);
  });
});
```

---

## Service Testing

### API Service Testing

Always test both success and error scenarios:

```typescript
// user-api.service.spec.ts
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';

describe('UserApiService', () => {
  let service: UserApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        UserApiService
      ]
    });
    service = TestBed.inject(UserApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('getAll', () => {
    it('should return transformed users on 200', () => {
      const apiResponse = [
        createUserApiResponse({ user_id: '1', first_name: 'John' })
      ];

      service.getAll().subscribe(users => {
        expect(users.length).toBe(1);
        expect(users[0].id).toBe('1');
        expect(users[0].name).toContain('John');
      });

      const req = httpMock.expectOne('/api/users');
      expect(req.request.method).toBe('GET');
      req.flush(apiResponse);
    });

    it('should handle 500 server error', () => {
      service.getAll().subscribe({
        next: () => fail('should have failed'),
        error: (error) => {
          expect(error.status).toBe(500);
        }
      });

      const req = httpMock.expectOne('/api/users');
      req.flush('Server Error', { status: 500, statusText: 'Internal Server Error' });
    });

    it('should handle 404 not found', () => {
      service.getAll().subscribe({
        next: () => fail('should have failed'),
        error: (error) => {
          expect(error.status).toBe(404);
        }
      });

      const req = httpMock.expectOne('/api/users');
      req.flush('Not Found', { status: 404, statusText: 'Not Found' });
    });
  });
});
```

### Testing Transformations

Test mapping logic in isolation:

```typescript
describe('mapToUser', () => {
  it('should transform snake_case to camelCase', () => {
    const apiResponse = createUserApiResponse({
      user_id: '123',
      first_name: 'John',
      last_name: 'Doe',
      is_active: 'Y'
    });

    const result = service['mapToUser'](apiResponse);

    expect(result).toEqual({
      id: '123',
      name: 'John Doe',
      email: expect.any(String),
      active: true
    });
  });

  it('should handle inactive users', () => {
    const apiResponse = createUserApiResponse({ is_active: 'N' });

    const result = service['mapToUser'](apiResponse);

    expect(result.active).toBe(false);
  });
});
```

---

## Interceptor Testing

Test interceptors by configuring them in the test module and verifying their behavior:

```typescript
// auth.interceptor.spec.ts
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let httpMock: HttpTestingController;
  let http: HttpClient;
  let oktaAuth: jest.Mocked<OktaAuthService>;

  beforeEach(() => {
    oktaAuth = {
      getAccessToken: jest.fn()
    } as any;

    TestBed.configureTestingModule({
      providers: [
        { provide: OktaAuthService, useValue: oktaAuth },
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting()
      ]
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should add Authorization header when token exists', async () => {
    oktaAuth.getAccessToken.mockResolvedValue('test-token');

    http.get('/api/users').subscribe();

    const req = httpMock.expectOne('/api/users');
    expect(req.request.headers.get('Authorization')).toBe('Bearer test-token');
    req.flush([]);
  });

  it('should skip auth for public endpoints', async () => {
    http.get('/public/health').subscribe();

    const req = httpMock.expectOne('/public/health');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({ status: 'ok' });
  });

  it('should proceed without token when none available', async () => {
    oktaAuth.getAccessToken.mockResolvedValue(null);

    http.get('/api/users').subscribe();

    const req = httpMock.expectOne('/api/users');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush([]);
  });
});
```

---

## NgRx Testing

NgRx code requires **100% coverage**. Follow patterns from the official NgRx documentation.

### Reducer Testing

Reducers are pure functions - easy to test:

```typescript
// user.reducer.spec.ts
describe('usersReducer', () => {
  describe('loadUsers action', () => {
    it('should set loading to true and clear error', () => {
      const initialState = createUsersState({ loading: false, error: 'previous error' });

      const result = usersReducer(initialState, UserActions.loadUsers());

      expect(result.loading).toBe(true);
      expect(result.error).toBeNull();
    });
  });

  describe('usersLoaded action', () => {
    it('should set users and loading to false', () => {
      const users = [createUser({ id: '1' }), createUser({ id: '2' })];
      const initialState = createUsersState({ loading: true });

      const result = usersReducer(initialState, UserActions.usersLoaded({ users }));

      expect(result.users).toEqual(users);
      expect(result.loading).toBe(false);
    });
  });

  describe('usersLoadFailed action', () => {
    it('should set error and loading to false', () => {
      const initialState = createUsersState({ loading: true });

      const result = usersReducer(
        initialState,
        UserActions.usersLoadFailed({ error: 'Network error' })
      );

      expect(result.error).toBe('Network error');
      expect(result.loading).toBe(false);
    });
  });
});
```

### Effects Testing

Use `provideMockActions` and `firstValueFrom` for cleaner async testing:

```typescript
// user.effects.spec.ts
import { firstValueFrom } from 'rxjs';

describe('UsersEffects', () => {
  let actions$: Observable<Action>;
  let effects: UsersEffects;
  let userApiService: jest.Mocked<UserApiService>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        UsersEffects,
        provideMockActions(() => actions$),
        {
          provide: UserApiService,
          useValue: {
            getAll: jest.fn()
          }
        }
      ]
    });

    effects = TestBed.inject(UsersEffects);
    userApiService = TestBed.inject(UserApiService) as jest.Mocked<UserApiService>;
  });

  describe('loadUsers$', () => {
    it('should return usersLoaded action on success', async () => {
      const users = [createUser({ id: '1' })];
      userApiService.getAll.mockReturnValue(of(users));
      actions$ = of(UserActions.loadUsers());

      const result = await firstValueFrom(effects.loadUsers$);

      expect(result).toEqual(UserActions.usersLoaded({ users }));
    });

    it('should return usersLoadFailed action on error', async () => {
      const error = new Error('Network error');
      userApiService.getAll.mockReturnValue(throwError(() => error));
      actions$ = of(UserActions.loadUsers());

      const result = await firstValueFrom(effects.loadUsers$);

      expect(result).toEqual(
        UserActions.usersLoadFailed({ error: 'Network error' })
      );
    });
  });
});
```

### Selector Testing

Test selectors with sample state:

```typescript
// user.selectors.spec.ts
describe('User Selectors', () => {
  describe('selectAllUsers', () => {
    it('should return all users', () => {
      const users = [createUser({ id: '1' }), createUser({ id: '2' })];
      const state = { users: createUsersState({ users }) };

      const result = selectAllUsers(state);

      expect(result).toEqual(users);
    });
  });

  describe('selectSelectedUser', () => {
    it('should return selected user', () => {
      const users = [createUser({ id: '1' }), createUser({ id: '2' })];
      const state = {
        users: createUsersState({ users, selectedUserId: '2' })
      };

      const result = selectSelectedUser(state);

      expect(result?.id).toBe('2');
    });

    it('should return null when no user selected', () => {
      const state = {
        users: createUsersState({ selectedUserId: null })
      };

      const result = selectSelectedUser(state);

      expect(result).toBeNull();
    });
  });
});
```

### Composed Selector Testing

For cross-feature selectors (see [[05-State-Management#Cross-Feature Selectors]]), test with combined state:

```typescript
// user.composed-selectors.spec.ts
describe('Composed Selectors', () => {
  describe('selectUsersInCurrentOrg', () => {
    it('should filter users by current organization', () => {
      const users = [
        createUser({ id: '1', organizationId: 'org-a' }),
        createUser({ id: '2', organizationId: 'org-b' }),
        createUser({ id: '3', organizationId: 'org-a' })
      ];
      const organization = createOrganization({ id: 'org-a' });

      const state = {
        users: createUsersState({ users }),
        organizations: createOrganizationsState({
          currentOrganization: organization
        })
      };

      const result = selectUsersInCurrentOrg(state);

      expect(result.length).toBe(2);
      expect(result.map(u => u.id)).toEqual(['1', '3']);
    });

    it('should return empty array when no organization selected', () => {
      const users = [createUser({ id: '1', organizationId: 'org-a' })];

      const state = {
        users: createUsersState({ users }),
        organizations: createOrganizationsState({
          currentOrganization: null
        })
      };

      const result = selectUsersInCurrentOrg(state);

      expect(result).toEqual([]);
    });
  });
});
```

---

## Test Fixtures

### Fixture File Convention

For every interface, create a companion fixture file:

```text
models/
├── user.model.ts
├── user.fixtures.ts        # Fixtures alongside interface
├── user-filters.model.ts
└── user-filters.fixtures.ts
```

### Fixture Pattern

Fixtures are simple creator functions with default parameters:

```typescript
// user.fixtures.ts
import { User } from './user.model';

export function createUser(overrides: Partial<User> = {}): User {
  return {
    id: 'default-id',
    name: 'Default User',
    email: 'default@example.com',
    active: true,
    ...overrides
  };
}
```

```typescript
// user-api.fixtures.ts
import { UserApiResponse } from '../api-types/user-api.types';

export function createUserApiResponse(
  overrides: Partial<UserApiResponse> = {}
): UserApiResponse {
  return {
    user_id: 'default-id',
    first_name: 'Default',
    last_name: 'User',
    email_address: 'default@example.com',
    is_active: 'Y',
    created_dt: '2026-01-01T00:00:00Z',
    modified_dt: '2026-01-01T00:00:00Z',
    department_cd: 'IT',
    ...overrides
  };
}
```

```typescript
// user.state.fixtures.ts
import { UsersState, initialUsersState } from './user.state';

export function createUsersState(overrides: Partial<UsersState> = {}): UsersState {
  return {
    ...initialUsersState,
    ...overrides
  };
}
```

### Using Fixtures in Tests

```typescript
// Consistent test data across all tests
it('should handle user with custom id', () => {
  const user = createUser({ id: 'custom-123' });
  // Uses defaults for all other properties
});

it('should handle inactive user', () => {
  const user = createUser({ active: false });
});

it('should handle multiple users', () => {
  const users = [
    createUser({ id: '1', name: 'Alice' }),
    createUser({ id: '2', name: 'Bob' })
  ];
});
```

### Benefits of This Pattern

| Benefit | Description |
|---------|-------------|
| **Consistency** | Same default values across all tests |
| **Maintainability** | Change defaults in one place |
| **Readability** | Tests show only relevant overrides |
| **Type safety** | Fixtures enforce interface compliance |
| **Reusability** | Can be used in code as constructors (rare) |

---

## E2E Testing

### Current State

E2E tests are currently managed externally by ATD testing teams. The direction is to bring E2E test code into application repositories.

### Future Direction

ATD is evaluating:

| Framework | Status | Notes |
|-----------|--------|-------|
| Playwright | **Evaluating** | Modern, fast, good DX |
| WebDriverIO | **Evaluating** | Better integration with ATD testing groups |
| Cypress | Not planned | |

### Preparation for In-Repo E2E

When adding E2E tests to repos:

```typescript
// Use data-testid for stable selectors
<button data-testid="submit-user-form">Submit</button>

// In test
await page.getByTestId('submit-user-form').click();
```

---

## CI Integration

### Test Execution in CI

Tests run as part of PR validation:

```yaml
# GitHub Actions
- name: Test affected
  run: npx nx affected -t test --base=origin/main

- name: Lint affected
  run: npx nx affected -t lint --base=origin/main

- name: Build affected
  run: npx nx affected -t build --base=origin/main
```

### Coverage Enforcement

CI fails if coverage drops below threshold:

```typescript
// jest.config.ts (or vitest.config.ts after migration)
export default {
  coverageThreshold: {
    global: {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    }
  }
};
```

> **Note:** ATD will migrate from Jest to Vitest with the Angular 21 upgrade (planned for 2026). Until then, use Jest. Vitest becomes the default test runner in Angular 21, and Nx will support the transition. The patterns in this document work with both runners.

### CI Checks

| Check | Requirement |
|-------|-------------|
| All tests pass | **Required** |
| Coverage threshold met | **Required** |
| Lint passes | **Required** |
| Build succeeds | **Required** |

All four gates must pass for PR to be mergeable.

---

## Anti-Patterns to Avoid

### Testing Implementation Details

```typescript
// WRONG: Testing private implementation
it('should call private helper', () => {
  const spy = jest.spyOn(component as any, '_privateHelper');
  component.publicMethod();
  expect(spy).toHaveBeenCalled();
});

// CORRECT: Test observable behavior
it('should produce expected output', () => {
  const result = component.publicMethod();
  expect(result).toBe('expected');
});
```

### Skipping Error Cases

```typescript
// WRONG: Only testing happy path
it('should return users', () => { /* 200 case */ });

// CORRECT: Test error scenarios too
it('should return users on 200', () => { /* ... */ });
it('should handle 500 error', () => { /* ... */ });
it('should handle 404 error', () => { /* ... */ });
```

### Scattered Test Data

```typescript
// WRONG: Magic values throughout tests
it('should find user', () => {
  const user = { id: '123', name: 'John', email: 'john@test.com' };
});

// CORRECT: Use fixtures with defaults
it('should find user', () => {
  const user = createUser({ id: '123' });
});
```

### Overusing Snapshot Tests

Snapshot tests are **not recommended** at ATD for most cases:

| Scenario | Recommendation |
|----------|----------------|
| Component templates | **Avoid** - brittle, hard to review |
| Large data structures | **Avoid** - use specific assertions |
| Generated code/configs | **Acceptable** - when structure matters |
| Error messages | **Acceptable** - when exact wording matters |

When you do use snapshots, keep them small and focused. Large snapshots become "approve and forget" rather than meaningful tests.

---

## Related Documents

- [[04-Component-Architecture]] - Component design for testability
- [[05-State-Management]] - NgRx patterns to test
- [[06-API-Integration]] - Service patterns to test
- [[10-CI-CD-Integration]] - Test automation in pipelines

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.3 | Clarified Vitest migration timeline: Jest until Angular 21 (2026), Vitest becomes default with Angular 21 |
| 2026-01-21 | 1.2 | Added signal testing patterns; added interceptor testing; added composed selector testing; updated to provideHttpClientTesting; noted Vitest migration; added snapshot testing guidance; updated effect testing with firstValueFrom |
| 2026-01-14 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
