---
title: "Common Pitfalls"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, pitfalls, anti-patterns]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# Common Pitfalls

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

This document catalogs common mistakes and anti-patterns encountered at ATD, with explanations of why they're problematic and how to fix them.

## Architecture Pitfalls

### God Components

**Problem:** Components that do too much - managing state, fetching data, containing business logic, and rendering UI.

```typescript
// WRONG: God component doing everything
@Component({ /* ... */ })
export class UserDashboardComponent implements OnInit {
  users: User[] = [];
  selectedUser: User | null = null;
  loading = false;
  error: string | null = null;
  filters: UserFilters = {};

  private readonly http = inject(HttpClient);

  ngOnInit(): void {
    this.loading = true;
    this.http.get<User[]>('/api/users').subscribe({
      next: users => {
        this.users = users;
        this.loading = false;
      },
      error: err => {
        this.error = err.message;
        this.loading = false;
      }
    });
  }

  filterUsers(): User[] {
    return this.users.filter(u => /* complex logic */);
  }

  selectUser(user: User): void {
    this.selectedUser = user;
    // More complex logic...
  }

  saveUser(user: User): void {
    this.http.put(`/api/users/${user.id}`, user).subscribe(/* ... */);
  }
}
```

**Why it's bad:**

- Difficult to test (too many responsibilities)
- Hard to reuse any part of it
- Change detection runs on everything
- Violates single responsibility principle

**Fix:** Split into smart/dumb pattern with NgRx:

```typescript
// CORRECT: Page component coordinates, dumb components render
@Component({
  selector: 'atd-user-dashboard-page',
  template: `
    @if (loading()) {
      <atd-spinner />
    } @else {
      <atd-user-filters
        [filters]="filters()"
        (filtersChanged)="onFiltersChanged($event)" />
      <atd-user-list
        [users]="filteredUsers()"
        (userSelected)="onUserSelected($event)" />
    }
  `
})
export class UserDashboardPageComponent {
  private readonly store = inject(Store);

  loading = this.store.selectSignal(selectLoading);
  filters = this.store.selectSignal(selectFilters);
  filteredUsers = this.store.selectSignal(selectFilteredUsers);

  onFiltersChanged(filters: UserFilters): void {
    this.store.dispatch(UserActions.setFilters({ filters }));
  }

  onUserSelected(user: User): void {
    this.store.dispatch(UserActions.selectUser({ user }));
  }
}
```

### NgRx in Dumb Components

**Problem:** Presentational components accessing the NgRx store directly.

```typescript
// WRONG: Dumb component accessing store
@Component({
  selector: 'atd-user-card'
})
export class UserCardComponent {
  private readonly store = inject(Store);  // Don't do this!

  user = input.required<User>();

  onClick(): void {
    this.store.dispatch(UserActions.selectUser({ user: this.user() }));
  }
}
```

**Why it's bad:**

- Couples component to global state
- Makes component harder to test
- Reduces reusability
- Violates separation of concerns

**Fix:** Emit events, let parent handle dispatch:

```typescript
// CORRECT: Dumb component emits event
@Component({
  selector: 'atd-user-card'
})
export class UserCardComponent {
  user = input.required<User>();
  selected = output<User>();

  onClick(): void {
    this.selected.emit(this.user());
  }
}

// Parent page component handles the action
onUserSelected(user: User): void {
  this.store.dispatch(UserActions.selectUser({ user }));
}
```

### Incorrect Lazy Loading

**Problem:** Loading all routes eagerly or breaking lazy loading with imports.

```typescript
// WRONG: Eager loading
export const routes: Routes = [
  { path: 'users', component: UserListPageComponent },
  { path: 'reports', component: ReportsPageComponent },
  { path: 'settings', component: SettingsPageComponent }
];

// WRONG: Importing component breaks lazy loading
import { UserListPageComponent } from './features/users/user-list-page.component';
// Now UserListPageComponent is in main bundle even if route is lazy!
```

**Fix:** Use `loadComponent` with dynamic imports:

```typescript
// CORRECT: Lazy load feature routes
export const routes: Routes = [
  {
    path: 'users',
    loadComponent: () => import('./features/users/user-list-page/user-list-page.component')
      .then(m => m.UserListPageComponent)
  },
  {
    path: 'reports',
    loadComponent: () => import('./features/reports/reports-page/reports-page.component')
      .then(m => m.ReportsPageComponent)
  }
];
```

### State Leaks Between Features

**Problem:** Sharing state incorrectly or not cleaning up when navigating away.

```typescript
// WRONG: Feature state persists when it shouldn't
// User selects item in Feature A, navigates to Feature B,
// returns to Feature A - stale selection is still there
```

**Fix:** Reset state on feature entry or use route guards:

```typescript
// Option 1: Reset in effect on feature entry
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.enterUsersFeature),
    tap(() => this.store.dispatch(UserActions.resetState())),
    switchMap(() => /* load fresh data */)
  )
);

// Option 2: Use resolver to ensure fresh state
export const usersResolver: ResolveFn<boolean> = () => {
  const store = inject(Store);
  store.dispatch(UserActions.resetState());
  store.dispatch(UserActions.loadUsers());

  // Wait for loading to complete before activating route
  return store.select(selectUsersLoaded).pipe(
    filter(loaded => loaded),
    take(1)
  );
};
```

---

## Performance Pitfalls

### Missing OnPush Change Detection

**Problem:** Using default change detection strategy.

```typescript
// WRONG: Default change detection
@Component({
  selector: 'atd-user-card',
  // Missing changeDetection property - defaults to Default
})
export class UserCardComponent {}
```

**Why it's bad:**

- Component re-renders on every change detection cycle
- Even when its inputs haven't changed
- Compounds quickly with many components

**Fix:** Always use OnPush:

```typescript
// CORRECT: OnPush change detection
@Component({
  selector: 'atd-user-card',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class UserCardComponent {}
```

### Function Calls in Templates

**Problem:** Calling functions in template expressions.

```typescript
// WRONG: Function called on every change detection
@Component({
  template: `
    <span>{{ formatDate(user.createdAt) }}</span>
    <span>{{ calculateAge(user.birthDate) }}</span>
    @for (user of filterUsers(searchTerm); track user.id) {
      ...
    }
  `
})
export class UserListComponent {
  formatDate(date: Date): string { /* ... */ }
  calculateAge(date: Date): number { /* ... */ }
  filterUsers(term: string): User[] { /* ... */ }
}
```

**Why it's bad:**

- Functions execute on every change detection cycle
- With OnPush, still runs when any input changes
- Expensive operations cause jank

**Fix:** Use pipes, signals, or selectors:

```typescript
// CORRECT: Use pipes for formatting
<span>{{ user.createdAt | date:'shortDate' }}</span>

// CORRECT: Use computed signals
formattedDate = computed(() => this.formatDate(this.user().createdAt));
filteredUsers = computed(() => this.filterByTerm(this.users(), this.searchTerm()));

// CORRECT: Use NgRx selectors for derived data
filteredUsers = this.store.selectSignal(selectFilteredUsers);
```

### Memory Leaks from Subscriptions

**Problem:** Subscribing to observables without unsubscribing.

```typescript
// WRONG: Memory leak - subscription never cleaned up
@Component({ /* ... */ })
export class LeakyComponent implements OnInit {
  data: Data[] = [];

  ngOnInit(): void {
    this.dataService.getData().subscribe(data => {
      this.data = data;  // Leaks when component destroyed!
    });
  }
}
```

**Why it's bad:**

- Subscription persists after component destruction
- Callback still fires, updating destroyed component
- Memory grows over time as users navigate

**Fix:** Use async pipe, signals, or `takeUntilDestroyed`:

```typescript
// BEST: Use selectSignal (NgRx)
data = this.store.selectSignal(selectData);

// GOOD: Use async pipe
data$ = this.dataService.getData();
// In template: {{ data$ | async }}

// ACCEPTABLE: takeUntilDestroyed when subscription unavoidable
private readonly destroyRef = inject(DestroyRef);

ngOnInit(): void {
  this.externalEvent$.pipe(
    takeUntilDestroyed(this.destroyRef)
  ).subscribe(event => this.handleEvent(event));
}
```

### Missing Track in @for Loops

**Problem:** Using `$index` instead of unique identifiers for tracking.

```typescript
// WRONG: Track by index - recreates DOM unnecessarily
@for (user of users(); track $index) {
  <atd-user-card [user]="user" />
}
```

**Why it's bad:**

- When array changes (sort, filter, add, remove), DOM is recreated
- Loses component state
- Poor performance with large lists

**Fix:** Track by unique identifier:

```typescript
// CORRECT: Track by unique ID
@for (user of users(); track user.id) {
  <atd-user-card [user]="user" />
}
```

### Bundle Bloat

**Problem:** Importing entire libraries or unnecessary code.

```typescript
// WRONG: Imports entire lodash (500KB+)
import * as _ from 'lodash';
const result = _.map(items, fn);

// WRONG: Barrel import pulls in everything
import { something } from '@big-library';
```

**Fix:** Import only what you need:

```typescript
// CORRECT: Import specific function
import map from 'lodash/map';
const result = map(items, fn);

// CORRECT: Use native JS when possible
const result = items.map(fn);

// CORRECT: Import specific exports
import { something } from '@big-library/something';
```

---

## Modern Angular Pitfalls

### Signal Misuse

**Problem:** Using signals incorrectly or unnecessarily.

```typescript
// WRONG: Creating signal from constant
const MAX_ITEMS = signal(100);  // Just use const

// WRONG: Modifying signal outside reactive context
someCallback() {
  this.data.set(newData);  // May not trigger CD if called from outside Angular
}

// WRONG: Using signal for derived data that should be computed
data = signal<User[]>([]);
filteredData = signal<User[]>([]);  // Should be computed!

onFilterChange(): void {
  this.filteredData.set(this.data().filter(/* ... */));  // Manual sync = bugs
}
```

**Fix:** Use signals appropriately:

```typescript
// CORRECT: Constants are just constants
const MAX_ITEMS = 100;

// CORRECT: Derived data uses computed
data = signal<User[]>([]);
filteredData = computed(() => this.data().filter(/* ... */));

// CORRECT: NgRx integration via selectSignal
users = this.store.selectSignal(selectUsers);
```

### Mixing Old and New Syntax

**Problem:** Inconsistent use of legacy and modern patterns.

```typescript
// INCONSISTENT: Mix of old and new
@Component({
  template: `
    <!-- Old directive -->
    <div *ngIf="loading">Loading...</div>

    <!-- New control flow -->
    @for (user of users(); track user.id) {
      <atd-user-card [user]="user" />
    }
  `
})
export class InconsistentComponent {
  // Old decorator input
  @Input() userId!: string;

  // New signal input
  userName = input<string>();

  // Mix of observable and signal
  loading$ = this.store.select(selectLoading);
  users = this.store.selectSignal(selectUsers);
}
```

**Fix:** Be consistent within a component:

```typescript
// CONSISTENT: All modern patterns
@Component({
  template: `
    @if (loading()) {
      <atd-spinner />
    }

    @for (user of users(); track user.id) {
      <atd-user-card [user]="user" />
    }
  `
})
export class ConsistentComponent {
  userId = input.required<string>();
  userName = input<string>();

  loading = this.store.selectSignal(selectLoading);
  users = this.store.selectSignal(selectUsers);
}
```

### Injection Context Errors

**Problem:** Using `inject()` outside valid injection context.

```typescript
// WRONG: inject() in callback
@Component({ /* ... */ })
export class BrokenComponent {
  ngOnInit(): void {
    setTimeout(() => {
      const router = inject(Router);  // ERROR: No injection context!
      router.navigate(['/']);
    }, 1000);
  }
}

// WRONG: inject() in plain function
function doSomething() {
  const http = inject(HttpClient);  // ERROR!
}
```

**Fix:** Inject in constructor/field initializer or pass as parameter:

```typescript
// CORRECT: Inject in field declaration
@Component({ /* ... */ })
export class WorkingComponent {
  private readonly router = inject(Router);

  ngOnInit(): void {
    setTimeout(() => {
      this.router.navigate(['/']);  // Uses pre-injected instance
    }, 1000);
  }
}

// CORRECT: Pass injected service to function
function doSomething(http: HttpClient) {
  // Use passed instance
}
```

---

## RxJS Pitfalls

### Nested Subscriptions

**Problem:** Subscribing inside a subscribe callback.

```typescript
// WRONG: Nested subscriptions
this.userId$.subscribe(userId => {
  this.userService.getUser(userId).subscribe(user => {
    this.addressService.getAddress(user.addressId).subscribe(address => {
      this.user = user;
      this.address = address;
    });
  });
});
```

**Why it's bad:**

- Creates multiple subscriptions hard to track
- Error handling is complicated
- Difficult to cancel properly

**Fix:** Use flattening operators:

```typescript
// CORRECT: Use switchMap/mergeMap
this.userId$.pipe(
  switchMap(userId => this.userService.getUser(userId)),
  switchMap(user => this.addressService.getAddress(user.addressId).pipe(
    map(address => ({ user, address }))
  )),
  takeUntilDestroyed(this.destroyRef)
).subscribe(({ user, address }) => {
  this.user = user;
  this.address = address;
});

// BETTER: Let NgRx effects handle this
// Component just dispatches action, effect handles the chain
```

### Overusing Subjects

**Problem:** Using Subjects when simpler patterns exist.

```typescript
// WRONG: Subject for simple event handling
@Component({ /* ... */ })
export class OvercomplicatedComponent {
  private readonly searchSubject = new BehaviorSubject<string>('');
  search$ = this.searchSubject.asObservable();

  onSearchChange(term: string): void {
    this.searchSubject.next(term);
  }
}
```

**Fix:** Use signals or simple patterns:

```typescript
// CORRECT: Signal for local state
searchTerm = signal('');

onSearchChange(term: string): void {
  this.searchTerm.set(term);
}

// CORRECT: Use model() for two-way binding with parent
searchTerm = model('');
// Parent binds: <child-component [(searchTerm)]="parentSearchTerm" />
// model() creates a writable signal that syncs with parent
```

### Not Handling Errors

**Problem:** Observables without error handling.

```typescript
// WRONG: No error handling
this.userService.getUsers().subscribe(users => {
  this.users = users;
});
// If API fails, observable errors and completes, app breaks silently
```

**Fix:** Always handle errors:

```typescript
// CORRECT: Handle errors in subscription
this.userService.getUsers().subscribe({
  next: users => this.users = users,
  error: err => this.handleError(err)
});

// BETTER: Let effects handle errors with failure actions
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userService.getUsers().pipe(
        map(users => UserActions.loadUsersSuccess({ users })),
        catchError(error => of(UserActions.loadUsersFailure({ error: error.message })))
      )
    )
  )
);
```

### Async/Await in Effects

**Problem:** Using async/await incorrectly in NgRx effects.

```typescript
// WRONG: async/await breaks the observable chain
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(async () => {
      const users = await firstValueFrom(this.userService.getUsers());
      return UserActions.loadUsersSuccess({ users });
    })
    // Error handling is lost, cancellation doesn't work properly
  )
);

// WRONG: Mixing async/await with pipe operators
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(async action => {
      try {
        const users = await this.userService.getUsers().toPromise();
        return UserActions.loadUsersSuccess({ users });
      } catch (error) {
        return UserActions.loadUsersFailure({ error });  // Lost in promise rejection
      }
    })
  )
);
```

**Why it's bad:**

- Breaks RxJS cancellation semantics (switchMap won't cancel in-flight requests)
- Error handling doesn't integrate with NgRx properly
- Loses the declarative nature of effects

**Fix:** Stay in the observable world:

```typescript
// CORRECT: Pure RxJS operators
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userService.getUsers().pipe(
        map(users => UserActions.loadUsersSuccess({ users })),
        catchError(error => of(UserActions.loadUsersFailure({ error: error.message })))
      )
    )
  )
);
```

---

## Testing Pitfalls

### Testing Implementation Details

**Problem:** Testing private methods or internal state instead of behavior.

```typescript
// WRONG: Testing private implementation
it('should call private helper', () => {
  const spy = jest.spyOn(component as any, '_processData');
  component.loadData();
  expect(spy).toHaveBeenCalled();  // Brittle - refactoring breaks test
});

// WRONG: Testing internal state
it('should set internal flag', () => {
  component.loadData();
  expect((component as any)._isProcessing).toBe(true);  // Implementation detail
});
```

**Fix:** Test observable behavior:

```typescript
// CORRECT: Test what the component does
it('should display processed data', () => {
  component.loadData();
  fixture.detectChanges();

  const displayedData = fixture.debugElement.query(By.css('.data-display'));
  expect(displayedData.nativeElement.textContent).toContain('Expected Result');
});

// CORRECT: Test public API
it('should emit event when action taken', () => {
  const emitSpy = jest.spyOn(component.dataLoaded, 'emit');
  component.loadData();
  expect(emitSpy).toHaveBeenCalledWith(expectedData);
});
```

### Over-Mocking

**Problem:** Mocking so much that tests don't verify real behavior.

```typescript
// WRONG: Everything is mocked
beforeEach(() => {
  mockUserService = { getUsers: jest.fn().mockReturnValue(of([])) };
  mockRouter = { navigate: jest.fn() };
  mockStore = { select: jest.fn(), dispatch: jest.fn() };
  mockActivatedRoute = { params: of({}) };
  // Test verifies mocks talk to each other, not real behavior
});
```

**Fix:** Use real implementations where practical:

```typescript
// CORRECT: Use MockStore with real selectors
beforeEach(() => {
  TestBed.configureTestingModule({
    imports: [UserListPageComponent],
    providers: [
      provideMockStore({
        initialState: { users: { users: [], loading: false } },
        selectors: [
          { selector: selectUsers, value: mockUsers },
          { selector: selectLoading, value: false }
        ]
      })
    ]
  });
});

// CORRECT: Use HttpTestingController for API tests
beforeEach(() => {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      UserApiService
    ]
  });
  httpMock = TestBed.inject(HttpTestingController);
});
```

### Async Test Issues

**Problem:** Not handling async operations properly in tests.

```typescript
// WRONG: Test completes before async operation
it('should load users', () => {
  component.loadUsers();
  expect(component.users.length).toBe(5);  // Fails - async not complete
});

// WRONG: Using real timers
it('should debounce search', () => {
  component.onSearch('test');
  setTimeout(() => {
    expect(component.searchResults.length).toBe(3);
  }, 500);  // Test completes before timeout!
});
```

**Fix:** Use proper async patterns:

```typescript
// CORRECT: Use fakeAsync for timers
it('should debounce search', fakeAsync(() => {
  component.onSearch('test');
  tick(300);  // Advance debounce time
  expect(component.searchResults.length).toBe(3);
}));

// CORRECT: Use waitForAsync for promises
it('should load users', waitForAsync(() => {
  component.loadUsers();
  fixture.whenStable().then(() => {
    expect(component.users.length).toBe(5);
  });
}));

// CORRECT: Subscribe and verify in callback
it('should emit result', (done) => {
  component.result$.subscribe(result => {
    expect(result).toBe('expected');
    done();
  });
  component.doAction();
});
```

### Brittle Tests

**Problem:** Tests that break with minor refactoring.

```typescript
// WRONG: Testing exact DOM structure
it('should render user', () => {
  expect(fixture.debugElement.query(By.css('div.user-container > span.user-name')))
    .toBeTruthy();  // Breaks if CSS classes change
});

// WRONG: Testing exact text
it('should show greeting', () => {
  expect(fixture.nativeElement.textContent).toBe('Hello, John!');  // Breaks if punctuation changes
});
```

**Fix:** Test semantics, not structure:

```typescript
// CORRECT: Use data-testid for stable selectors
// In template: <span data-testid="user-name">{{ user.name }}</span>
it('should display user name', () => {
  const userName = fixture.debugElement.query(By.css('[data-testid="user-name"]'));
  expect(userName.nativeElement.textContent).toContain('John');
});

// CORRECT: Test presence of key content
it('should greet user', () => {
  expect(fixture.nativeElement.textContent).toContain('John');
});
```

---

## How to Fix Common Issues

### Diagnosis Techniques

| Symptom | Likely Cause | Diagnostic Tool |
|---------|--------------|-----------------|
| Slow rendering | Change detection, missing OnPush | Angular DevTools profiler |
| Memory growth | Subscription leaks | Chrome DevTools Memory |
| Large bundle | Improper imports, no lazy loading | webpack-bundle-analyzer |
| Stale data | State not reset, caching issues | Redux DevTools |
| Tests fail intermittently | Async timing issues | Run with `--detectOpenHandles` |

### Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| Missing OnPush | Add `changeDetection: ChangeDetectionStrategy.OnPush` |
| Subscription leak | Replace `.subscribe()` with `\| async` or `selectSignal` |
| Function in template | Create `computed()` signal or use pipe |
| NgRx in dumb component | Move store access to parent, emit events |
| Eager route loading | Change `component:` to `loadComponent:` with dynamic import |
| Track by index | Change `track $index` to `track item.id` |

### When to Ask for Help

Escalate to senior developers when:

- Performance issues persist after applying standard patterns
- Memory leaks not traceable to obvious sources
- Architectural decisions needed (state management approach)
- Build/bundling issues not resolved by standard fixes

---

## Related Documents

- [[02-Modern-Angular-Patterns]] - Correct patterns to follow
- [[04-Component-Architecture]] - Smart/dumb component patterns
- [[05-State-Management]] - Proper NgRx patterns
- [[08-Performance-Optimization]] - Performance best practices
- [[11-Code-Review-Standards]] - Catching issues in review
- [[17-Production-Support]] - Debugging production issues

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Updated to signal inputs/outputs, fixed model() example, added async/await in effects pitfall, updated HTTP testing to provideHttpClientTesting() |
| 2026-01-19 | 1.1 | Full content added: architecture, performance, Angular, RxJS, testing pitfalls |
| 2026-01-08 | 1.0 | Initial stub created |
