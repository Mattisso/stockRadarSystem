---
title: "Modern Angular Patterns"
created: 2026-01-08 10:00
updated: 2026-01-13 09:00
tags: [playbook, angular, work, atd-standards, signals, standalone, architecture]
context: Angular Development Playbook for ATD
status: active
angular_version: "18-20+"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# Modern Angular Patterns

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

This document covers modern Angular patterns from versions 18-20+ that ATD has adopted. It will evolve as Angular continues to mature.

> **Note on Code Examples:** Throughout this document, templates are shown inline within `@Component` decorators for brevity. **ATD requires separate template files** (`.component.html`) in actual code. Always use `templateUrl` pointing to an external file rather than inline `template` strings.

## Pattern Overview

| Pattern | Introduced | ATD Stance |
|---------|------------|------------|
| Standalone Components | v14+ | **Required** |
| Lazy Loading | v2+ (improved) | **Expected default** |
| `OnPush` Change Detection | v2+ | **Required** |
| Signal-based inputs/outputs | v17+ (stable v18) | **Required** for new code |
| New Control Flow (`@if`, `@for`) | v17+ | **Required** |
| `inject()` Function | v14+ | **Required** for new code |
| Zoneless Change Detection | v18+ (stable v20.2, default v21) | **Required** for new projects |

---

## Standalone Components

### Why Standalone Is Required

Standalone components eliminate NgModule boilerplate and provide:

- **Simpler mental model** - Components declare their own dependencies
- **Better tree-shaking** - Unused code more easily eliminated
- **Easier lazy loading** - Direct `loadComponent()` without module wrappers
- **Cleaner architecture** - No artificial module boundaries

### ATD Standalone Policy

- **All new components must be standalone**
- **NgModules**: Avoid. Rare exceptions require lead/architect approval with clear justification.

### Creating Standalone Components

```typescript
@Component({
  selector: 'app-user-card',
  standalone: true,
  imports: [CommonModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (user) {
      <div class="user-card">
        <h3>{{ user.name }}</h3>
        <a [routerLink]="['/users', user.id]">View Profile</a>
      </div>
    }
  `
})
export class UserCardComponent {
  @Input() user: User | null = null;
}
```

### Provider Patterns

Use functional providers instead of module-based providers:

```typescript
// app.config.ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAnimations(),
    provideStore({ user: userReducer }),
    provideEffects([UserEffects]),
  ]
};

// main.ts
bootstrapApplication(AppComponent, appConfig);
```

---

## Component Organization

### Page Component Pattern

ATD organizes components around **page folders** using a smart/dumb component pattern. Each component lives in its own named subfolder with the standard 4 Angular files:

```text
features/
└── users/
    └── user-list-page/                          # Page-level folder
        ├── user-list-page/                      # Smart component folder
        │   ├── user-list-page.component.ts      # Smart component (NgRx)
        │   ├── user-list-page.component.html
        │   ├── user-list-page.component.scss
        │   └── user-list-page.component.spec.ts
        ├── user-table/                          # Dumb component folder
        │   ├── user-table.component.ts
        │   ├── user-table.component.html
        │   ├── user-table.component.scss
        │   └── user-table.component.spec.ts
        ├── user-filters/                        # Dumb component folder
        │   ├── user-filters.component.ts
        │   ├── user-filters.component.html
        │   ├── user-filters.component.scss
        │   └── user-filters.component.spec.ts
        └── user-card/                           # Dumb component folder
            ├── user-card.component.ts
            ├── user-card.component.html
            ├── user-card.component.scss
            └── user-card.component.spec.ts
```

### Smart vs Dumb Components

| Smart (Page) Components | Dumb (Presentational) Components |
|------------------------|----------------------------------|
| Interface with NgRx store | Use signal inputs (`input()`, `output()`) |
| Dispatch actions | Emit events to parent |
| Select state | No service dependencies |
| Handle routing | Pure, easily testable |
| One per "page" | Many per page |

**Smart component example:**

```typescript
@Component({
  selector: 'app-user-list-page',
  standalone: true,
  imports: [UserTableComponent, UserFiltersComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-user-filters
      [currentFilters]="filters()"
      (filtersChanged)="onFiltersChanged($event)"
    />
    <app-user-table
      [users]="users()"
      [loading]="loading()"
      (userSelected)="onUserSelected($event)"
    />
  `
})
export class UserListPageComponent {
  private readonly store = inject(Store);

  users = this.store.selectSignal(selectUsers);
  loading = this.store.selectSignal(selectLoading);
  filters = this.store.selectSignal(selectFilters);

  onFiltersChanged(filters: UserFilters): void {
    this.store.dispatch(UserActions.setFilters({ filters }));
  }

  onUserSelected(user: User): void {
    this.store.dispatch(UserActions.selectUser({ user }));
  }
}
```

**Dumb component example:**

```typescript
@Component({
  selector: 'app-user-table',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (loading) {
      <div class="loading-spinner">Loading...</div>
    } @else {
      <table>
        @for (user of users; track user.id) {
          <tr (click)="userSelected.emit(user)">
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
          </tr>
        }
      </table>
    }
  `
})
export class UserTableComponent {
  users = input<User[]>([]);
  loading = input(false);
  userSelected = output<User>();
}
```

### Component Promotion Path

When components are reused:

1. **Single page** → Keep in page folder
2. **Multiple pages in feature** → Move to `features/shared/`
3. **Multiple features in app** → Move to `app/shared/`
4. **Multiple apps** → Promote to `libs/shared/ui`

**Accelerated promotion:** If a developer believes a component is truly reusable and broadly useful from the start, they may promote directly to `libs/` without following each intermediate step. Use judgment—don't prematurely abstract, but don't artificially slow down obviously reusable components either.

---

## Change Detection

### OnPush Is Required

**All components at ATD use `OnPush` change detection.**

```typescript
@Component({
  // ...
  changeDetection: ChangeDetectionStrategy.OnPush
})
```

Benefits:

- Better performance (only checks when inputs change or events fire)
- Encourages immutable data patterns
- Prepares codebase for zoneless Angular

### Avoid Zone-Dependent Patterns

Zone-dependent patterns are **code smells** and should be remediated:

| Avoid | Why | Alternative |
|-------|-----|-------------|
| `ChangeDetectorRef.detectChanges()` | Zone dependency | Use signals or async pipe |
| `ChangeDetectorRef.markForCheck()` | Zone dependency | Use signals or push new input reference |
| `setTimeout()` for change detection | Hacky workaround | Fix the actual reactivity issue |
| `ApplicationRef.tick()` | Zone dependency | Proper state management |

---

## Signals

### When to Use Signals vs Observables

| Use Signals For | Use Observables For |
|-----------------|---------------------|
| Component local state | HTTP responses |
| Computed/derived values | Complex async streams |
| Simple reactivity | Debounce, throttle, merge |
| Template binding | Event coordination across services |
| Form field values | WebSocket streams |

### ATD Signal Guidelines

- **New code only** - Not migrating existing RxJS patterns right now
- **Keep it simple** - Use for straightforward reactive state
- **Pair with NgRx** - Store handles global state, signals for local UI state

### Basic Signal Usage

```typescript
@Component({
  // ...
})
export class CounterComponent {
  // Create a signal
  count = signal(0);

  // Update with set
  reset(): void {
    this.count.set(0);
  }

  // Update with update (access previous value)
  increment(): void {
    this.count.update(c => c + 1);
  }
}
```

### Computed Signals

Derived values that automatically update:

```typescript
@Component({
  // ...
})
export class CartComponent {
  items = signal<CartItem[]>([]);
  taxRate = signal(0.08);

  // Automatically recalculates when items or taxRate change
  subtotal = computed(() =>
    this.items().reduce((sum, item) => sum + item.price * item.quantity, 0)
  );

  tax = computed(() => this.subtotal() * this.taxRate());

  total = computed(() => this.subtotal() + this.tax());
}
```

### Effects

For side effects when signals change:

```typescript
@Component({
  // ...
})
export class SearchComponent {
  searchTerm = signal('');

  constructor() {
    // Runs whenever searchTerm changes
    effect(() => {
      console.log('Search term changed:', this.searchTerm());
      // Analytics, localStorage, etc.
    });
  }
}
```

---

## New Control Flow Syntax

### Required for All New Code

The new control flow syntax replaces structural directives. **Migrate existing `*ngIf`/`*ngFor` when touching those files.**

### @if / @else

```html
<!-- Old -->
<div *ngIf="user; else noUser">
  Welcome, {{ user.name }}
</div>
<ng-template #noUser>Please log in</ng-template>

<!-- New -->
@if (user) {
  <div>Welcome, {{ user.name }}</div>
} @else {
  <div>Please log in</div>
}
```

With `else if`:

```html
@if (status === 'loading') {
  <app-spinner />
} @else if (status === 'error') {
  <app-error [message]="errorMessage" />
} @else {
  <app-content [data]="data" />
}
```

### @for with track

```html
<!-- Old -->
<div *ngFor="let user of users; trackBy: trackByUserId">
  {{ user.name }}
</div>

<!-- New -->
@for (user of users; track user.id) {
  <div>{{ user.name }}</div>
} @empty {
  <div>No users found</div>
}
```

#### Track Expression Guide

The `track` expression is **required** and critical for performance. It tells Angular how to identify items when the array changes.

| Scenario | Track Expression | Why |
|----------|------------------|-----|
| Items have unique ID | `track item.id` | Best performance, stable identity |
| Items have unique composite key | `track item.type + '-' + item.code` | When no single ID exists |
| Primitive array (strings, numbers) | `track $index` | No object identity available |
| Items never reorder/change | `track $index` | Acceptable for static lists |
| Items frequently reorder | `track item.id` | **Never** use `$index` |

**Choosing the right track expression:**

1. **Prefer stable unique identifiers** (`id`, `uuid`, `slug`)
   - Best performance when items reorder, add, or remove
   - Angular reuses DOM elements correctly

2. **Use `$index` only when:**
   - Array contains primitives (strings, numbers)
   - List is static and never reorders
   - Items genuinely have no unique identifier

3. **Avoid `$index` when:**
   - Items can be reordered (drag/drop, sorting)
   - Items can be inserted/removed from middle
   - Items have any unique property available

**Example - why track matters:**

```html
<!-- BAD: Using $index with re-orderable list -->
@for (task of tasks; track $index) {
  <app-task-card [task]="task" />  <!-- All cards re-render on reorder! -->
}

<!-- GOOD: Using stable ID -->
@for (task of tasks; track task.id) {
  <app-task-card [task]="task" />  <!-- Only moved cards update DOM position -->
}
```

### @switch

```html
<!-- Old -->
<div [ngSwitch]="status">
  <span *ngSwitchCase="'active'">Active</span>
  <span *ngSwitchCase="'inactive'">Inactive</span>
  <span *ngSwitchDefault>Unknown</span>
</div>

<!-- New -->
@switch (status) {
  @case ('active') {
    <span>Active</span>
  }
  @case ('inactive') {
    <span>Inactive</span>
  }
  @default {
    <span>Unknown</span>
  }
}
```

---

## inject() Function

### Required for New Code

Use `inject()` instead of constructor injection for all new components and services.

```typescript
// Required: inject()
@Component({
  // ...
})
export class UserProfileComponent {
  private readonly userService = inject(UserService);
  private readonly route = inject(ActivatedRoute);
  private readonly store = inject(Store);

  @Input() userId!: string;
  @Output() profileUpdated = new EventEmitter<User>();

  // Component logic...
}

// Avoid: constructor injection
@Component({
  // ...
})
export class UserProfileComponent {
  constructor(
    private userService: UserService,
    private route: ActivatedRoute,
    private store: Store
  ) {}
}
```

### Placement Convention

**Place `inject()` calls early in the class, before `@Input()` and `@Output()` for discoverability:**

```typescript
export class MyComponent {
  // 1. Injected dependencies (first)
  private readonly store = inject(Store);
  private readonly router = inject(Router);

  // 2. Inputs and Outputs
  @Input() data: SomeData;
  @Output() action = new EventEmitter<void>();

  // 3. Signals and other state
  loading = signal(false);

  // 4. Computed values
  derivedValue = computed(() => /* ... */);

  // 5. Methods
}
```

### Migration

Migrating constructor injection to `inject()` is **optional** when touching existing files (unlike control flow syntax which should be migrated).

### Functional Patterns with inject()

`inject()` enables extracting logic to reusable functions:

```typescript
// Reusable injection function
function injectUserPermissions() {
  const store = inject(Store);
  const permissions = store.selectSignal(selectUserPermissions);

  return {
    canEdit: computed(() => permissions().includes('edit')),
    canDelete: computed(() => permissions().includes('delete')),
    canAdmin: computed(() => permissions().includes('admin')),
  };
}

// Usage in component
@Component({
  // ...
})
export class AdminPanelComponent {
  private readonly permissions = injectUserPermissions();

  handleDelete(): void {
    if (this.permissions.canDelete()) {
      // proceed
    }
  }
}
```

---

## Lazy Loading

### Expected Default

Lazy loading is **expected for all applications** unless there's a very strong justification not to use it (e.g., very small internal-only apps).

Benefits:

- Smaller initial bundle
- Faster initial load
- Load features on demand

### Route-Level Lazy Loading

```typescript
// app.routes.ts
export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./home/home-page.component')
      .then(m => m.HomePageComponent)
  },
  {
    path: 'users',
    loadComponent: () => import('./users/user-list-page/user-list-page.component')
      .then(m => m.UserListPageComponent)
  },
  {
    path: 'admin',
    loadChildren: () => import('./admin/admin.routes')
      .then(m => m.ADMIN_ROUTES),
    canActivate: [authGuard]
  }
];
```

### Lazy Loading with Standalone Components

No module wrapper needed:

```typescript
// Direct component loading
{
  path: 'dashboard',
  loadComponent: () => import('./dashboard/dashboard-page.component')
    .then(m => m.DashboardPageComponent)
}

// Route group with child routes
// admin/admin.routes.ts
export const ADMIN_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () => import('./admin-layout.component')
      .then(m => m.AdminLayoutComponent),
    children: [
      {
        path: 'users',
        loadComponent: () => import('./admin-users/admin-users-page.component')
          .then(m => m.AdminUsersPageComponent)
      },
      {
        path: 'settings',
        loadComponent: () => import('./admin-settings/admin-settings-page.component')
          .then(m => m.AdminSettingsPageComponent)
      }
    ]
  }
];
```

---

## Zoneless Change Detection

### ATD ZonelessPolicy

**All new projects must use zoneless Angular.** Zone.js should only be used if absolutely necessary (rare third-party library incompatibility).

**Existing projects** migrate opportunistically—there is no fixed timeline or urgency to migrate running applications. When touching code in existing zoned applications, follow these guidelines:

- New components should be zoneless-ready (OnPush, signals)
- Don't introduce new zone-dependent patterns
- Migrate to zoneless when a major refactor provides the opportunity

### Why Zoneless

- Better performance (no zone.js overhead)
- Predictable change detection
- Smaller bundle size
- Required for some server environments

### Preparing for Zoneless

ATD's current practices already prepare us:

| Practice | Zoneless Ready? |
|----------|-----------------|
| OnPush everywhere | ✅ Yes |
| Signals for state | ✅ Yes |
| No `detectChanges()` calls | ✅ Yes |
| Async pipe / signal binding | ✅ Yes |

### Enabling Zoneless

Zoneless change detection became stable in **Angular 20.2** and is the **default for new projects in Angular 21**. Use the stable API:

```typescript
// app.config.ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    // ... other providers
  ]
};
```

> **Note:** The experimental API `provideExperimentalZonelessChangeDetection()` is deprecated. Migrate to `provideZonelessChangeDetection()` when upgrading to Angular 20.2+.

---

## Deprecated Patterns to Avoid

| Pattern | Problem | Use Instead |
|---------|---------|-------------|
| NgModules for features | Unnecessary complexity | Standalone components |
| `*ngIf`, `*ngFor`, `*ngSwitch` | Legacy syntax | `@if`, `@for`, `@switch` |
| Constructor injection | Less flexible | `inject()` function |
| Default change detection | Performance issues | `OnPush` |
| `detectChanges()` / `markForCheck()` | Zone dependency | Signals, proper reactivity |
| `setTimeout()` for CD hacks | Code smell | Fix underlying issue |

---

## Related Documents

- [[01-Getting-Started]] - Environment setup
- [[04-Component-Architecture]] - Detailed component patterns
- [[05-State-Management]] - NgRx and signals for state
- [[14-Migration-Guides]] - Version migration guides

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.3 | Signal-based inputs/outputs now required for new code; clarified zoneless policy (required for new projects, opportunistic for existing); updated examples to use signal inputs |
| 2026-01-13 | 1.2 | Corrected page folder structure; added notes on inline templates and accelerated promotion; updated zoneless to stable API (v20.2) |
| 2026-01-12 | 1.1 | Full content added, renamed to version-agnostic |
| 2026-01-08 | 1.0 | Initial stub created |
