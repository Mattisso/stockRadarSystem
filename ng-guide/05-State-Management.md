---
title: "State Management"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, state-management, signals, ngrx]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [intermediate, experienced-developers]
---

# State Management

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## State Management Decision Guide

### NgRx Is the Default

**NgRx is the default choice for all ATD applications.** Not using NgRx is the exception, not the rule.

This simplifies decision-making and reduces cognitive load:

| Scenario | Choice |
|----------|--------|
| App calls backend services | **NgRx** |
| Cross-feature state | **NgRx** |
| Complex async flows | **NgRx** |
| Any new application | **NgRx** |
| Local UI state only (toggles, form fields) | Signals |

### Simple Decision Rule

> If it hits a backend → **NgRx**
> If it's just local UI → **Signals**

### When Signals Are Appropriate

Signals are for component-scoped UI state that doesn't leave the component:

```typescript
@Component({ /* ... */ })
export class UserFiltersComponent {
  // Local UI state - signals are fine
  isExpanded = signal(false);
  selectedTab = signal<'active' | 'all'>('active');

  // Form field state
  searchTerm = signal('');
}
```

### NgRx selectSignal vs Plain Signals

Understanding when to use `store.selectSignal()` versus plain `signal()`:

| Use Case | Approach | Why |
|----------|----------|-----|
| **Global/shared state** | `store.selectSignal(selector)` | State managed by NgRx store, shared across components |
| **Local UI state in dumb components** | `signal()` | Component-internal, no external dependencies |
| **Local UI state in smart components** | `signal()` | UI toggles, form fields before submission |
| **Derived from store state** | `computed()` with `selectSignal` | Combine multiple store selections |

**Example: Smart component with both patterns**

```typescript
@Component({ /* ... */ })
export class UserListPageComponent {
  private readonly store = inject(Store);

  // NgRx selectSignal - global state from store
  users = this.store.selectSignal(selectAllUsers);
  loading = this.store.selectSignal(selectUsersLoading);

  // Plain signals - local UI state
  isFilterPanelOpen = signal(false);
  viewMode = signal<'grid' | 'list'>('list');

  // Computed combining store and local state
  displayedUsers = computed(() => {
    const allUsers = this.users();
    return this.viewMode() === 'grid' ? allUsers.slice(0, 12) : allUsers;
  });
}
```

**Example: Dumb component (plain signals only)**

```typescript
@Component({ /* ... */ })
export class UserFiltersComponent {
  // Inputs from parent (also signals)
  currentFilters = input<UserFilters>();

  // Local UI state - plain signals only, no store access
  isExpanded = signal(false);
  tempSearchTerm = signal('');

  // Output to parent
  filtersChanged = output<UserFilters>();
}
```

**Key principle:** Dumb components never access the NgRx store. They use plain signals for internal UI state and communicate via inputs/outputs.

---

## NgRx Structure

### Feature Store Organization

ATD uses feature stores with a `+state/` folder convention:

```text
features/
└── users/
    ├── +state/
    │   ├── user.actions.ts
    │   ├── user.reducer.ts
    │   ├── user.effects.ts
    │   ├── user.selectors.ts
    │   ├── user.composed-selectors.ts  # Cross-feature selectors
    │   └── user.state.ts               # State interface
    ├── user-list-page/
    └── user-detail-page/
```

### Provider Pattern for Feature Stores

Create a provider function for each feature to enable dynamic loading:

```typescript
// users/+state/users.providers.ts
import { provideState, provideEffects } from '@ngrx/store';
import { usersReducer } from './user.reducer';
import { UsersEffects } from './user.effects';

export function provideUsersState() {
  return [
    provideState('users', usersReducer),
    provideEffects(UsersEffects)
  ];
}
```

This allows:

- Lazy loading state with routes
- Eager effect registration when needed
- Clean feature encapsulation

```typescript
// In routes
{
  path: 'users',
  loadComponent: () => import('./user-list-page/user-list-page.component'),
  providers: [provideUsersState()]
}
```

---

## Actions

### Naming Convention

Use bracketed group and descriptive name: `[Group] Action Name`

### Multi-Action Pattern

ATD uses a multi-action structure that separates intent from outcome:

```typescript
// 1. Initiate action - dispatched from component, handled by effect
export const loadUsers = createAction('[Users] Load Users');

// 2. Past-tense actions - dispatched from effect, handled by reducer
export const usersLoaded = createAction(
  '[Users] Users Loaded',
  props<{ users: User[] }>()
);

export const usersLoadFailed = createAction(
  '[Users] Users Load Failed',
  props<{ error: string }>()
);
```

**Why this pattern works:**

| Action | Dispatched By | Handled By | Purpose |
|--------|---------------|------------|---------|
| `loadUsers` | Component | Effect | Express intent |
| `usersLoaded` | Effect | Reducer | Update state on success |
| `usersLoadFailed` | Effect | Reducer | Update state on failure |

This pattern (from Victor Savkin) provides:

- Clear separation of concerns
- Easy-to-follow action flow
- Consistent naming across features

### Action Creator Patterns

**Use `createActionGroup` for all new action files.** It enforces consistent naming and groups related actions:

```typescript
// user.actions.ts
import { createActionGroup, emptyProps, props } from '@ngrx/store';

export const UserActions = createActionGroup({
  source: 'Users',
  events: {
    // Initiate actions (present tense)
    'Load Users': emptyProps(),
    'Load User': props<{ id: string }>(),
    'Create User': props<{ user: User }>(),
    'Update User': props<{ user: User }>(),
    'Delete User': props<{ id: string }>(),

    // Result actions (past tense)
    'Users Loaded': props<{ users: User[] }>(),
    'User Loaded': props<{ user: User }>(),
    'User Created': props<{ user: User }>(),
    'User Updated': props<{ user: User }>(),
    'User Deleted': props<{ id: string }>(),

    // Failure actions
    'Users Load Failed': props<{ error: string }>(),
    'User Operation Failed': props<{ error: string }>(),
  }
});
```

---

## Reducers

### State Interface

```typescript
// user.state.ts
export interface UsersState {
  users: User[];
  selectedUserId: string | null;
  loading: boolean;
  error: string | null;
}

export const initialUsersState: UsersState = {
  users: [],
  selectedUserId: null,
  loading: false,
  error: null
};
```

### Reducer Implementation

```typescript
// user.reducer.ts
import { createReducer, on } from '@ngrx/store';
import { UserActions } from './user.actions';
import { initialUsersState } from './user.state';

export const usersReducer = createReducer(
  initialUsersState,

  // Handle initiate action - set loading
  on(UserActions.loadUsers, state => ({
    ...state,
    loading: true,
    error: null
  })),

  // Handle success - update data
  on(UserActions.usersLoaded, (state, { users }) => ({
    ...state,
    users,
    loading: false
  })),

  // Handle failure - set error
  on(UserActions.usersLoadFailed, (state, { error }) => ({
    ...state,
    loading: false,
    error
  }))
);
```

### Entity Adapter

For collections, `@ngrx/entity` provides optimized CRUD operations:

```typescript
// user.state.ts
import { EntityState, EntityAdapter, createEntityAdapter } from '@ngrx/entity';

export interface UsersState extends EntityState<User> {
  selectedUserId: string | null;
  loading: boolean;
  error: string | null;
}

export const usersAdapter: EntityAdapter<User> = createEntityAdapter<User>({
  selectId: user => user.id,
  sortComparer: (a, b) => a.name.localeCompare(b.name)
});

export const initialUsersState: UsersState = usersAdapter.getInitialState({
  selectedUserId: null,
  loading: false,
  error: null
});
```

```typescript
// user.reducer.ts
export const usersReducer = createReducer(
  initialUsersState,

  on(UserActions.usersLoaded, (state, { users }) =>
    usersAdapter.setAll(users, { ...state, loading: false })
  ),

  on(UserActions.userCreated, (state, { user }) =>
    usersAdapter.addOne(user, state)
  ),

  on(UserActions.userUpdated, (state, { user }) =>
    usersAdapter.updateOne({ id: user.id, changes: user }, state)
  ),

  on(UserActions.userDeleted, (state, { id }) =>
    usersAdapter.removeOne(id, state)
  )
);
```

Entity adapter is used at ATD but less frequently than bare state. Use it when:

- Managing collections with frequent CRUD operations
- Need optimized lookups by ID
- Want built-in selectors for entities

---

## Effects

### Basic Effect Pattern

Effects handle async operations and translate initiate actions to result actions:

```typescript
// user.effects.ts
@Injectable()
export class UsersEffects {
  private readonly actions$ = inject(Actions);
  private readonly userService = inject(UserService);

  loadUsers$ = createEffect(() =>
    this.actions$.pipe(
      ofType(UserActions.loadUsers),
      switchMap(() =>
        this.userService.getAll().pipe(
          map(users => UserActions.usersLoaded({ users })),
          catchError(error => of(UserActions.usersLoadFailed({ error: error.message })))
        )
      )
    )
  );
}
```

### Accessing State in Effects

Use `concatLatestFrom` to access current state:

```typescript
loadUserDetails$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUserDetails),
    concatLatestFrom(() => this.store.select(selectCurrentUserId)),
    switchMap(([action, userId]) =>
      this.userService.getDetails(userId).pipe(
        map(user => UserActions.userDetailsLoaded({ user })),
        catchError(error => of(UserActions.userOperationFailed({ error: error.message })))
      )
    )
  )
);
```

`concatLatestFrom` is preferred over `withLatestFrom` because it subscribes to the selector lazily—only after the action arrives. With `withLatestFrom`, the selector subscription happens immediately when the effect initializes, which can cause issues if the state slice isn't loaded yet (returning `undefined` or stale values).

### Factor Logic to Helper Services

**Don't inline complex logic in effects.** Extract to helper services:

```typescript
// WRONG: Too much logic in effect
loadAndTransformUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userService.getAll().pipe(
        map(users => {
          // Don't do this - complex transformation inline
          const transformed = users
            .filter(u => u.active)
            .map(u => ({ ...u, displayName: `${u.first} ${u.last}` }))
            .sort((a, b) => a.displayName.localeCompare(b.displayName));
          return UserActions.usersLoaded({ users: transformed });
        })
      )
    )
  )
);

// CORRECT: Logic in helper service
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userService.getAll().pipe(
        map(users => this.userHelper.transformForDisplay(users)),
        map(users => UserActions.usersLoaded({ users }))
      )
    )
  )
);
```

### Error Handling Patterns

#### Basic Error Handling

```typescript
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userService.getAll().pipe(
        map(users => UserActions.usersLoaded({ users })),
        catchError(error => of(UserActions.usersLoadFailed({ error: error.message })))
      )
    )
  )
);
```

#### Retry Logic

```typescript
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(UserActions.loadUsers),
    switchMap(() =>
      this.userService.getAll().pipe(
        retry({ count: 3, delay: 1000 }),
        map(users => UserActions.usersLoaded({ users })),
        catchError(error => of(UserActions.usersLoadFailed({ error: error.message })))
      )
    )
  )
);
```

#### Global Error Handling

Create a centralized error effect. Define a type guard for error actions:

```typescript
// shared/+state/error.types.ts
interface ErrorAction {
  type: string;
  error: string;
}

function isErrorAction(action: { type: string }): action is ErrorAction {
  return action.type.includes('Failed') && 'error' in action;
}

// shared/+state/global.effects.ts
@Injectable()
export class GlobalEffects {
  private readonly actions$ = inject(Actions);
  private readonly errorService = inject(ErrorService);

  handleErrors$ = createEffect(() =>
    this.actions$.pipe(
      filter(isErrorAction),
      tap(action => this.errorService.handle(action.error))
    ),
    { dispatch: false }
  );
}
```

---

## Selectors

### Basic Selectors

```typescript
// user.selectors.ts
import { createFeatureSelector, createSelector } from '@ngrx/store';
import { UsersState } from './user.state';

export const selectUsersState = createFeatureSelector<UsersState>('users');

export const selectAllUsers = createSelector(
  selectUsersState,
  state => state.users
);

export const selectUsersLoading = createSelector(
  selectUsersState,
  state => state.loading
);

export const selectUsersError = createSelector(
  selectUsersState,
  state => state.error
);

export const selectSelectedUserId = createSelector(
  selectUsersState,
  state => state.selectedUserId
);

export const selectSelectedUser = createSelector(
  selectAllUsers,
  selectSelectedUserId,
  (users, selectedId) => users.find(u => u.id === selectedId) ?? null
);
```

### Entity Adapter Selectors

```typescript
// With entity adapter
const { selectAll, selectEntities, selectIds, selectTotal } = usersAdapter.getSelectors();

export const selectAllUsers = createSelector(selectUsersState, selectAll);
export const selectUserEntities = createSelector(selectUsersState, selectEntities);
export const selectUserIds = createSelector(selectUsersState, selectIds);
export const selectUserCount = createSelector(selectUsersState, selectTotal);
```

### Cross-Feature Selectors

To avoid circular references, use a separate file for composed selectors:

```typescript
// user.composed-selectors.ts
import { createSelector } from '@ngrx/store';
import { selectAllUsers } from './user.selectors';
import { selectCurrentOrganization } from '../../organizations/+state/organization.selectors';

export const selectUsersInCurrentOrg = createSelector(
  selectAllUsers,
  selectCurrentOrganization,
  (users, org) => users.filter(u => u.organizationId === org?.id)
);
```

**File structure**:

- `user.selectors.ts` - Local selectors only, no cross-feature imports
- `user.composed-selectors.ts` - Can import from other features

### Using Selectors in Components

**Preferred: `selectSignal()` (returns Signal)**

```typescript
export class UserListPageComponent {
  private readonly store = inject(Store);

  users = this.store.selectSignal(selectAllUsers);
  loading = this.store.selectSignal(selectUsersLoading);

  // Template: {{ users() }}
}
```

`selectSignal()` integrates with Angular's signals direction, works with `computed()` and `effect()`, and doesn't require the async pipe.

**Alternative: `select()` with async pipe (returns Observable)**

Existing code using `select()` is acceptable and need not be migrated:

```typescript
export class UserListPageComponent {
  private readonly store = inject(Store);

  users$ = this.store.select(selectAllUsers);
  loading$ = this.store.select(selectUsersLoading);

  // Template: @for (user of users$ | async; track user.id) { ... }
}
```

---

## Signal-Based Local State

For component-scoped UI state, use signals:

```typescript
@Component({ /* ... */ })
export class UserFiltersComponent {
  // UI state - doesn't need NgRx
  isAdvancedMode = signal(false);
  selectedTab = signal<'active' | 'inactive' | 'all'>('all');

  // Computed from local state
  showAdvancedFilters = computed(() => this.isAdvancedMode());

  toggleAdvancedMode(): void {
    this.isAdvancedMode.update(v => !v);
  }
}
```

### When to Keep State Local

| Keep Local (Signals) | Move to NgRx |
|---------------------|--------------|
| Toggle open/closed | User selection affects other features |
| Form field values (pre-submit) | Loaded from backend |
| Component animation state | Needs persistence |
| Temporary UI filters | Affects URL/routing |

### Note on @ngrx/signals

NgRx provides `@ngrx/signals` with `signalStore` for signal-based reactive state management. ATD currently uses the traditional NgRx store pattern documented above. If evaluating `signalStore` for new features, discuss with the team first to maintain consistency.

---

## Development Tools

### NgRx DevTools

Install the Redux DevTools browser extension and configure in your app:

```typescript
// app.config.ts
import { provideStoreDevtools } from '@ngrx/store-devtools';

export const appConfig: ApplicationConfig = {
  providers: [
    provideStore(),
    provideStoreDevtools({
      maxAge: 25,
      logOnly: !isDevMode()
    })
  ]
};
```

DevTools enable time-travel debugging, action inspection, and state diffing during development.

---

## Anti-Patterns to Avoid

### Overusing Global State

```typescript
// WRONG: Local UI state in NgRx
export const toggleFilterPanel = createAction('[Filters] Toggle Panel');

// CORRECT: Local signal
isFilterPanelOpen = signal(false);
```

### State Mutation

```typescript
// WRONG: Mutating state
on(UserActions.usersLoaded, (state, { users }) => {
  state.users = users; // Mutation!
  return state;
})

// CORRECT: Return new object
on(UserActions.usersLoaded, (state, { users }) => ({
  ...state,
  users
}))
```

### Services Dispatching Actions

```typescript
// WRONG: Service dispatches action
@Injectable()
export class UserService {
  private readonly http = inject(HttpClient);
  private readonly store = inject(Store);

  loadUsers(): void {
    this.http.get<User[]>('/api/users').subscribe(users => {
      this.store.dispatch(usersLoaded({ users })); // Don't do this!
    });
  }
}

// CORRECT: Component dispatches, effect handles async
// Component:
this.store.dispatch(UserActions.loadUsers());

// Effect handles the rest
```

### Giant Effects Files

```typescript
// WRONG: All logic inline in effect
someEffect$ = createEffect(() => /* 50 lines of transformation logic */);

// CORRECT: Extract to helper service
someEffect$ = createEffect(() =>
  this.actions$.pipe(
    ofType(someAction),
    switchMap(action => this.helperService.process(action))
  )
);
```

---

## Related Documents

- [[02-Modern-Angular-Patterns]] - Signals overview
- [[04-Component-Architecture]] - Smart/dumb component patterns
- [[06-API-Integration]] - Service patterns with NgRx
- [[07-Testing-Strategies]] - Testing effects, reducers, and selectors

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.3 | Added detailed NgRx selectSignal vs plain signals decision guidance with examples |
| 2026-01-21 | 1.2 | Clarified createActionGroup as preferred; marked selectSignal as preferred; added type-safe error handling; added signalStore note; added DevTools section; improved concatLatestFrom explanation; added Testing link |
| 2026-01-14 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
