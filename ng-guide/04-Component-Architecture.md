---
title: "Component Architecture"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, architecture, components]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# Component Architecture

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

This document covers component architecture patterns and conventions at ATD. For modern Angular patterns (signals, control flow, inject), see [[02-Modern-Angular-Patterns]].

## Standalone Component Standard

All ATD components are standalone. Here's the standard configuration:

```typescript
@Component({
  selector: 'atd-user-card',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './user-card.component.html',
  styleUrl: './user-card.component.scss'
})
export class UserCardComponent {
  private readonly store = inject(Store);

  userId = input.required<string>();
  selected = output<string>();
}
```

> **Note:** Signal-based inputs (`input()`, `output()`) are **required** for all new components. Existing code using `@Input()` and `@Output()` decorators is acceptable in legacy code and need not be migrated unless the component is being significantly refactored.

### Required Configuration

| Setting | Requirement |
|---------|-------------|
| `standalone` | Always `true` |
| `changeDetection` | Always `OnPush` |
| `templateUrl` | External file required (no inline templates) |
| `styleUrl` | External file required (no inline styles) |
| `selector` | Use `atd-` prefix |

### Import Management

**Use tsconfig path aliases for cross-library imports**, not relative paths:

```typescript
// Correct: tsconfig alias
import { UserService } from '@atd/user-api';
import { ButtonComponent } from '@atd/ui-button';

// Wrong: relative cross-library path
import { UserService } from '../../../libs/user-api/src/lib/user.service';
import { ButtonComponent } from '../../../libs/ui-button/src/lib/button.component';
```

Configure aliases in `tsconfig.base.json`:

```json
{
  "compilerOptions": {
    "paths": {
      "@atd/user-api": ["libs/user-api/src/index.ts"],
      "@atd/ui-button": ["libs/ui-button/src/index.ts"]
    }
  }
}
```

---

## Component Categories

### Overview

| Category | Purpose | Naming | NgRx Access |
|----------|---------|--------|-------------|
| **Page** | Smart/container, route entry point | `-page` suffix | Yes |
| **Presentational** | Dumb, inputs/outputs only | No suffix | No |
| **Layout** | Shell/wrapper structure | `-layout`, `-shell` | Minimal |
| **UI Primitive** | Reusable UI elements | `atd-` prefix | No |

### Page Components (Smart)

Page components are the "smart" containers that:

- Connect to NgRx store
- Dispatch actions
- Coordinate child components
- Serve as route entry points

```typescript
@Component({
  selector: 'atd-user-list-page',
  standalone: true,
  imports: [AsyncPipe, UserTableComponent, UserFiltersComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './user-list-page.component.html',
  styleUrl: './user-list-page.component.scss'
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

### Presentational Components (Dumb)

Presentational components:

- **Require** signal inputs (`input()`, `output()`) for new components
- Have no service dependencies
- Contain no business logic
- Are easily testable

```typescript
@Component({
  selector: 'atd-user-table',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './user-table.component.html',
  styleUrl: './user-table.component.scss'
})
export class UserTableComponent {
  users = input<User[]>([]);
  loading = input(false);
  userSelected = output<User>();
}
```

### Layout Components

Layout components provide structural wrappers:

```typescript
// Shell layout with header, sidebar, content
@Component({
  selector: 'atd-main-layout',
  standalone: true,
  imports: [RouterOutlet, HeaderComponent, SidebarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './main-layout.component.html',
  styleUrl: './main-layout.component.scss'
})
export class MainLayoutComponent {}
```

```html
<!-- main-layout.component.html -->
<atd-header />
<div class="layout-container">
  <atd-sidebar />
  <main class="content">
    <ng-content select="[content]" />
  </main>
</div>
```

---

## Component Communication

### Input/Output Patterns

**Traditional decorators:**

```typescript
export class UserCardComponent {
  @Input() user!: User;
  @Input() highlighted = false;
  @Output() selected = new EventEmitter<User>();
}
```

**Signal-based inputs (required for new code):**

```typescript
export class UserCardComponent {
  user = input.required<User>();
  highlighted = input(false);
  selected = output<User>();

  // Two-way binding
  searchTerm = model('');
}
```

### Communication Patterns

| Pattern | Use Case |
|---------|----------|
| Signal inputs (`input()`, `output()`) | Parent-child communication (**required** for new code) |
| `@Input()` / `@Output()` | Legacy code only (acceptable, no migration required) |
| `model()` | Two-way binding with signals |
| NgRx Store | Cross-feature state, complex state |
| Services | Sibling communication, shared utilities |

### NgRx Integration

Smart components dispatch actions; they typically don't call services directly. Effects handle async work—see [[05-State-Management]] for effect patterns.

```typescript
// Page component dispatches actions
onSave(user: User): void {
  this.store.dispatch(UserActions.saveUser({ user }));
}
```

---

## Anti-Patterns to Avoid

### NgRx in Dumb Components

```typescript
// WRONG: Dumb component accessing store
@Component({ /* ... */ })
export class UserCardComponent {
  private readonly store = inject(Store); // Don't do this!

  onClick(): void {
    this.store.dispatch(/* ... */); // Don't do this!
  }
}

// CORRECT: Emit event, let parent handle
@Component({ /* ... */ })
export class UserCardComponent {
  clicked = output<void>();

  onClick(): void {
    this.clicked.emit();
  }
}
```

### Logic in Components

```typescript
// WRONG: Business logic in component
export class UserListPageComponent {
  filterUsers(users: User[], term: string): User[] {
    return users.filter(u =>
      u.name.toLowerCase().includes(term.toLowerCase()) ||
      u.email.toLowerCase().includes(term.toLowerCase())
    );
  }
}

// CORRECT: Logic in selector or service
// In selectors.ts
export const selectFilteredUsers = createSelector(
  selectUsers,
  selectSearchTerm,
  (users, term) => users.filter(u => /* ... */)
);
```

### Data Fetching in Components

```typescript
// WRONG: Fetching data directly in component
export class UserListPageComponent implements OnInit {
  users: User[] = [];

  ngOnInit(): void {
    this.userService.getUsers().subscribe(users => {
      this.users = users; // Don't do this!
    });
  }
}
```

**Correct approaches:**

1. **Route resolver** - Good for simple data loading before navigation:

```typescript
export const usersResolver: ResolveFn<User[]> = () => {
  return inject(UserService).getUsers();
};

// In routes
{
  path: 'users',
  component: UserListPageComponent,
  resolve: { users: usersResolver }
}
```

1. **NgRx action dispatch** - Preferred for complex state or when data is shared across components. See [[05-State-Management]] for details:

```typescript
export class UserListPageComponent {
  private readonly store = inject(Store);
  users = this.store.selectSignal(selectUsers);

  ngOnInit(): void {
    this.store.dispatch(UserActions.loadUsers());
  }
}
```

### Subscribing in Components

```typescript
// WRONG: Manual subscription
export class UserListPageComponent implements OnInit, OnDestroy {
  private subscription!: Subscription;
  users: User[] = [];

  ngOnInit(): void {
    this.subscription = this.store.select(selectUsers).subscribe(
      users => this.users = users
    );
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }
}

// CORRECT: Use selectSignal or async pipe
export class UserListPageComponent {
  users = this.store.selectSignal(selectUsers);
}

// Or in template with async pipe
// users$ = this.store.select(selectUsers);
// @for (user of users$ | async; track user.id) { ... }
```

If you must subscribe, use `takeUntilDestroyed()`:

```typescript
export class MyComponent {
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.someObservable$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(/* ... */);
  }
}
```

---

## Component Lifecycle

### Field Initialization vs ngOnInit

| Location | Use For |
|----------|---------|
| Field declarations | `inject()` calls, simple initialization |
| `ngOnInit` | Logic that depends on decorator-based `@Input()` values |
| `effect()` | Reactive logic with signal inputs (see [[02-Modern-Angular-Patterns]]) |

**With signal inputs**, use `effect()` or `computed()` instead of `ngOnInit`:

```typescript
export class UserDetailComponent {
  private readonly store = inject(Store);

  userId = input.required<string>();

  constructor() {
    effect(() => {
      this.store.dispatch(UserActions.loadUser({ id: this.userId() }));
    });
  }
}
```

**With decorator-based inputs** (existing code), `ngOnInit` is still appropriate:

```typescript
export class UserDetailComponent {
  private readonly store = inject(Store);

  @Input() userId!: string;

  ngOnInit(): void {
    this.store.dispatch(UserActions.loadUser({ id: this.userId }));
  }
}
```

**Do not create a constructor just for `inject()` calls.** Use field declarations instead. For comprehensive `inject()` patterns, see [[02-Modern-Angular-Patterns]].

```typescript
// Preferred: inject as fields
export class MyComponent {
  private readonly store = inject(Store);
  private readonly router = inject(Router);
}

// Avoid: unnecessary constructor
export class MyComponent {
  constructor() {
    this.store = inject(Store);
    this.router = inject(Router);
  }
}
```

### Lifecycle Hooks

| Hook | Use Case | Frequency at ATD |
|------|----------|------------------|
| `ngOnInit` | Input-dependent initialization (decorator inputs) | Occasional (use `effect()` with signal inputs) |
| `ngOnChanges` | React to input changes (decorator inputs) | Rare (use `effect()` with signal inputs) |
| `ngOnDestroy` | Manual cleanup | Rare (use `takeUntilDestroyed`) |
| `afterNextRender` | DOM manipulation after first render | Very rare |
| `afterRender` | DOM manipulation after every render | Very rare |

### Cleanup Patterns

With async pipe and signals, `ngOnDestroy` is rarely needed. When you must subscribe:

```typescript
export class MyComponent {
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.externalEvent$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(event => this.handleEvent(event));
  }
}
```

---

## Content Projection

### Always Use Named Slots

ATD uses named slots almost exclusively, even for single projections.

> **Note:** Template shown separately below for clarity. In actual code, both component and template follow the Required Configuration above.

```typescript
@Component({
  selector: 'atd-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './card.component.html',
  styleUrl: './card.component.scss'
})
export class CardComponent {}
```

```html
<!-- card.component.html -->
<div class="card">
  <header class="card-header">
    <ng-content select="[cardHeader]" />
  </header>
  <div class="card-body">
    <ng-content select="[cardBody]" />
  </div>
  <footer class="card-footer">
    <ng-content select="[cardFooter]" />
  </footer>
</div>
```

Usage:

```html
<atd-card>
  <h2 cardHeader>User Details</h2>
  <div cardBody>
    <p>{{ user.name }}</p>
    <p>{{ user.email }}</p>
  </div>
  <button cardFooter (click)="save()">Save</button>
</atd-card>
```

---

## Dynamic Components

Dynamic component loading is rare at ATD. When needed:

```typescript
@Component({ /* ... */ })
export class DynamicHostComponent {
  private readonly viewContainerRef = inject(ViewContainerRef);

  async loadComponent(): Promise<void> {
    const { MyDynamicComponent } = await import('./my-dynamic.component');
    this.viewContainerRef.createComponent(MyDynamicComponent);
  }
}
```

Prefer route-based lazy loading over dynamic component loading when possible.

---

## Naming Conventions

### File Naming

| Item | Convention | Example |
|------|------------|---------|
| Component file | kebab-case | `user-card.component.ts` |
| Template | Same name | `user-card.component.html` |
| Styles | Same name | `user-card.component.scss` |
| Spec file | Same folder | `user-card.component.spec.ts` |
| Page component | `-page` suffix | `user-list-page.component.ts` |

### Selector and Class Naming

| Item | Convention | Example |
|------|------------|---------|
| Selector | `atd-` prefix, kebab-case | `atd-user-card` |
| Class | PascalCase, `Component` suffix | `UserCardComponent` |
| Page selector | `atd-` prefix, `-page` suffix | `atd-user-list-page` |
| Page class | PascalCase, `PageComponent` suffix | `UserListPageComponent` |

### Folder Structure

Nested structure within page folders—each component gets its own subfolder:

```text
features/
└── users/
    └── user-list-page/                      # Page-level folder
        ├── user-list-page/                  # Smart component subfolder
        │   ├── user-list-page.component.ts
        │   ├── user-list-page.component.html
        │   ├── user-list-page.component.scss
        │   └── user-list-page.component.spec.ts
        ├── user-table/                      # Dumb component subfolder
        │   ├── user-table.component.ts
        │   ├── user-table.component.html
        │   ├── user-table.component.scss
        │   └── user-table.component.spec.ts
        └── user-filters/                    # Dumb component subfolder
            ├── user-filters.component.ts
            ├── user-filters.component.html
            ├── user-filters.component.scss
            └── user-filters.component.spec.ts
```

**Do not create a generic `components/` subfolder**—child components nest directly in their own named subfolders within the page folder.

### Services, Pipes, and Directives

Follow standard Angular naming conventions:

| Item | File Name | Class Name |
|------|-----------|------------|
| Service | `user.service.ts` | `UserService` |
| Pipe | `format-date.pipe.ts` | `FormatDatePipe` |
| Directive | `highlight.directive.ts` | `HighlightDirective` |

---

## Related Documents

- [[02-Modern-Angular-Patterns]] - Signals, control flow, inject()
- [[03-Nx-Workspace-Setup]] - Library organization and promotion
- [[05-State-Management]] - NgRx patterns and state in components
- [[12-ATD-Conventions]] - Full naming conventions

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.3 | Signal inputs now required for new code (not just preferred); updated folder structure to nested pattern; clarified decorator patterns for legacy only |
| 2026-01-21 | 1.2 | Updated examples to prefer signal inputs; clarified data fetching approaches; simplified NgRx/inject sections with references to related docs; added signal-era lifecycle guidance |
| 2026-01-14 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
