---
title: "Migration Guides"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, migration, upgrade]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [experienced-developers, tech-leads]
---

# Migration Guides

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

This document provides guidance for migrating Angular applications at ATD, including version upgrades and pattern modernization.

## Angular Version Upgrades

### General Upgrade Process

ATD follows a structured approach to Angular version upgrades:

```text
1. Review release notes and breaking changes
2. Update Angular Update Guide selections
3. Create upgrade branch
4. Run automated migrations
5. Fix manual migration issues
6. Update dependencies
7. Run tests and verify
8. Code review and merge
```

### Using the Angular Update Guide

The official [Angular Update Guide](https://angular.dev/update-guide) is the starting point for all upgrades:

1. Select your current and target versions
2. Select your application complexity
3. Follow the generated checklist

### Upgrade Commands

```bash
# Update Angular CLI and core
npx ng update @angular/cli @angular/core

# Update Angular Material (if used)
npx ng update @angular/material

# Update Nx workspace (run after Angular)
npx nx migrate latest
npx nx migrate --run-migrations

# Check for outdated packages
npm outdated
```

### Pre-Upgrade Checklist

Before starting an upgrade:

- [ ] All tests passing on current version
- [ ] No pending PRs to main
- [ ] Review Angular release notes
- [ ] Check third-party library compatibility
- [ ] Notify team of upgrade window
- [ ] Create upgrade branch from main

### Post-Upgrade Verification

After completing upgrade:

- [ ] `npx nx affected -t lint` passes
- [ ] `npx nx affected -t test` passes
- [ ] `npx nx affected -t build` passes
- [ ] Manual smoke test of key features
- [ ] Performance spot check (no regressions)

---

## NgModule to Standalone Migration

### Overview

ATD requires standalone components for all new code. Legacy NgModule-based code should be migrated when touched.

### Automated Migration

Angular provides a schematic for automated migration:

```bash
# Migrate entire application
npx ng generate @angular/core:standalone

# Options:
# - Convert all components, directives, and pipes to standalone
# - Remove unnecessary NgModule classes
# - Update bootstrap to use standalone API
```

### Manual Migration Steps

**Step 1: Convert Component to Standalone**

```typescript
// BEFORE: NgModule-based
@Component({
  selector: 'atd-user-card',
  templateUrl: './user-card.component.html'
})
export class AtdUserCardComponent {
  @Input() user!: User;
}

@NgModule({
  declarations: [AtdUserCardComponent],
  imports: [CommonModule],
  exports: [AtdUserCardComponent]
})
export class AtdUserCardModule {}
```

```typescript
// AFTER: Standalone
// Note: standalone: true is the default in Angular 19+, shown here for clarity
@Component({
  selector: 'atd-user-card',
  imports: [CommonModule],  // Move imports here
  templateUrl: './user-card.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AtdUserCardComponent {
  @Input() user!: User;
}
// Delete the NgModule file entirely
```

**Step 2: Update Consumers**

```typescript
// BEFORE: Import module
@NgModule({
  imports: [AtdUserCardModule]
})
export class AtdFeatureModule {}

// AFTER: Import component directly
@Component({
  imports: [AtdUserCardComponent]  // Import component, not module
})
export class AtdFeatureComponent {}
```

**Step 3: Update Bootstrap (if applicable)**

```typescript
// BEFORE: NgModule bootstrap
// main.ts
platformBrowserDynamic().bootstrapModule(AppModule);

// AFTER: Standalone bootstrap
// main.ts
bootstrapApplication(AppComponent, appConfig);

// app.config.ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideStore(),
    provideEffects([UserEffects])
  ]
};
```

### Migration Priority

| Priority | What to Migrate |
|----------|-----------------|
| **High** | Shared library components (affects many consumers) |
| **Medium** | Feature modules actively being modified |
| **Low** | Stable legacy features not being touched |

### Common Migration Issues

| Issue | Solution |
|-------|----------|
| Circular dependency after migration | Extract shared components to separate file |
| Missing imports in standalone | Add all required imports to component |
| Provider scope changes | Use `providedIn: 'root'` or route providers |
| Lazy loaded module providers | Move to route-level `providers` array |

---

## Control Flow Migration

### Overview

ATD requires modern control flow syntax (`@if`, `@for`, `@switch`) for all new code. Legacy directive syntax should be migrated when touching a file.

### Automated Migration

```bash
# Migrate control flow syntax
npx ng generate @angular/core:control-flow
```

### Manual Migration Patterns

**@if Migration**

```html
<!-- BEFORE -->
<div *ngIf="loading">Loading...</div>
<div *ngIf="user; else noUser">{{ user.name }}</div>
<ng-template #noUser>No user</ng-template>

<!-- AFTER -->
@if (loading) {
  <div>Loading...</div>
}

@if (user) {
  <div>{{ user.name }}</div>
} @else {
  <div>No user</div>
}
```

**@for Migration**

```html
<!-- BEFORE -->
<div *ngFor="let user of users; let i = index; trackBy: trackByUserId">
  {{ i }}: {{ user.name }}
</div>

<!-- AFTER -->
@for (user of users; track user.id; let i = $index) {
  <div>{{ i }}: {{ user.name }}</div>
} @empty {
  <div>No users found</div>
}
```

**@switch Migration**

```html
<!-- BEFORE -->
<div [ngSwitch]="status">
  <span *ngSwitchCase="'active'">Active</span>
  <span *ngSwitchCase="'inactive'">Inactive</span>
  <span *ngSwitchDefault>Unknown</span>
</div>

<!-- AFTER -->
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

### Migration Tips

| Tip | Reason |
|-----|--------|
| Migrate entire template at once | Avoid mixing old/new in same file |
| Update imports | Remove `CommonModule` if only using control flow |
| Check `track` expression | Ensure unique identifier, not `$index` |

---

## Signal Migration

### Overview

ATD prefers signals for reactive state. Migration from observables to signals should be done incrementally.

### When to Migrate

| Scenario | Migrate? |
|----------|----------|
| New component | Start with signals |
| Touching existing component | Migrate if practical |
| Complex RxJS chains | Keep as observables |
| Simple state display | Migrate to signals |

### Migration Patterns

**Observable to Signal (Store)**

```typescript
// BEFORE: Observable subscription
@Component({
  template: `
    <div *ngIf="loading$ | async">Loading...</div>
    <div *ngFor="let user of users$ | async">{{ user.name }}</div>
  `
})
export class UserListComponent {
  loading$ = this.store.select(selectLoading);
  users$ = this.store.select(selectUsers);
}

// AFTER: Signal-based
@Component({
  template: `
    @if (loading()) {
      <div>Loading...</div>
    }
    @for (user of users(); track user.id) {
      <div>{{ user.name }}</div>
    }
  `
})
export class UserListComponent {
  loading = this.store.selectSignal(selectLoading);
  users = this.store.selectSignal(selectUsers);
}
```

**Local State to Signal**

```typescript
// BEFORE: Class properties
export class FormComponent {
  isSubmitting = false;
  errorMessage: string | null = null;

  submit(): void {
    this.isSubmitting = true;
    this.service.submit().subscribe({
      error: err => {
        this.errorMessage = err.message;
        this.isSubmitting = false;
      }
    });
  }
}

// AFTER: Signals
export class FormComponent {
  isSubmitting = signal(false);
  errorMessage = signal<string | null>(null);

  submit(): void {
    this.isSubmitting.set(true);
    this.service.submit().subscribe({
      error: err => {
        this.errorMessage.set(err.message);
        this.isSubmitting.set(false);
      }
    });
  }
}
```

**toSignal() for Observables**

```typescript
// Convert observable to signal
import { toSignal } from '@angular/core/rxjs-interop';

export class MyComponent {
  private readonly route = inject(ActivatedRoute);

  // Convert route params to signal
  userId = toSignal(
    this.route.params.pipe(map(p => p['id'])),
    { initialValue: '' }
  );
}
```

### What NOT to Migrate

Keep as observables (see [[06-API-Integration]] and [[05-State-Management]] for patterns):

- Complex RxJS chains with operators (debounce, distinctUntilChanged, etc.)
- NgRx effects that need observable patterns
- External library integrations expecting observables

---

## Input/Output Migration

### Signal Inputs

Migrate `@Input()` to signal-based inputs:

```typescript
// BEFORE: Decorator inputs
export class UserCardComponent {
  @Input() user!: User;
  @Input() showActions = true;
}

// AFTER: Signal inputs
export class UserCardComponent {
  user = input.required<User>();
  showActions = input(true);
}
```

**Usage changes:**

```typescript
// BEFORE: Access directly
this.user.name

// AFTER: Call as function
this.user().name
```

### Model Inputs (Two-Way Binding)

```typescript
// BEFORE: Input + Output pattern
export class ToggleComponent {
  @Input() checked = false;
  @Output() checkedChange = new EventEmitter<boolean>();

  toggle(): void {
    this.checked = !this.checked;
    this.checkedChange.emit(this.checked);
  }
}

// AFTER: Model input
export class ToggleComponent {
  checked = model(false);

  toggle(): void {
    this.checked.update(v => !v);
  }
}
```

### Output Migration

```typescript
// BEFORE: EventEmitter
export class ButtonComponent {
  @Output() clicked = new EventEmitter<void>();
}

// AFTER: output() function
export class ButtonComponent {
  clicked = output<void>();
}
```

---

## Dependency Injection Migration

### Constructor to inject() Function

Migrate from constructor-based DI to the `inject()` function:

```typescript
// BEFORE: Constructor injection
@Component({
  selector: 'atd-user-profile',
  templateUrl: './user-profile.component.html'
})
export class AtdUserProfileComponent {
  constructor(
    private readonly userService: UserService,
    private readonly router: Router,
    private readonly store: Store,
    @Inject(APP_CONFIG) private readonly config: AppConfig
  ) {}
}

// AFTER: inject() function
@Component({
  selector: 'atd-user-profile',
  templateUrl: './user-profile.component.html'
})
export class AtdUserProfileComponent {
  private readonly userService = inject(UserService);
  private readonly router = inject(Router);
  private readonly store = inject(Store);
  private readonly config = inject(APP_CONFIG);
}
```

### Benefits of inject()

| Benefit | Description |
|---------|-------------|
| Cleaner syntax | No constructor boilerplate |
| Works in functions | Can use in route guards, interceptors |
| Type inference | Better TypeScript integration |
| Inheritance friendly | No super() call needed |

### Optional Dependencies

```typescript
// BEFORE: @Optional() decorator
constructor(@Optional() private analytics?: AnalyticsService) {}

// AFTER: inject() with options
private readonly analytics = inject(AnalyticsService, { optional: true });
```

### Injection in Functions

```typescript
// Route guard using inject()
export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }
  return router.createUrlTree(['/login']);
};

// HTTP interceptor using inject()
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const token = authService.getToken();

  if (token) {
    req = req.clone({
      setHeaders: { Authorization: `Bearer ${token}` }
    });
  }
  return next(req);
};
```

---

## View Query Migration

### ViewChild to viewChild()

Migrate `@ViewChild()` to signal-based queries:

```typescript
// BEFORE: Decorator-based
@Component({
  template: `<input #searchInput />`
})
export class AtdSearchComponent implements AfterViewInit {
  @ViewChild('searchInput') searchInput!: ElementRef<HTMLInputElement>;

  ngAfterViewInit(): void {
    this.searchInput.nativeElement.focus();
  }
}

// AFTER: Signal-based
@Component({
  template: `<input #searchInput />`
})
export class AtdSearchComponent {
  searchInput = viewChild.required<ElementRef<HTMLInputElement>>('searchInput');

  constructor() {
    afterNextRender(() => {
      this.searchInput().nativeElement.focus();
    });
  }
}
```

### ContentChild to contentChild()

```typescript
// BEFORE: Decorator-based
@Component({
  selector: 'atd-card'
})
export class AtdCardComponent {
  @ContentChild(AtdCardHeaderComponent) header?: AtdCardHeaderComponent;
}

// AFTER: Signal-based
@Component({
  selector: 'atd-card'
})
export class AtdCardComponent {
  header = contentChild(AtdCardHeaderComponent);
}
```

### ViewChildren to viewChildren()

```typescript
// BEFORE: Decorator-based
@Component({
  template: `
    @for (item of items(); track item.id) {
      <atd-list-item [item]="item" />
    }
  `
})
export class AtdListComponent {
  @ViewChildren(AtdListItemComponent) listItems!: QueryList<AtdListItemComponent>;
}

// AFTER: Signal-based
@Component({
  template: `
    @for (item of items(); track item.id) {
      <atd-list-item [item]="item" />
    }
  `
})
export class AtdListComponent {
  listItems = viewChildren(AtdListItemComponent);
}
```

### Query Signal Benefits

| Feature | Decorator | Signal |
|---------|-----------|--------|
| Reactive updates | Manual subscription to changes | Automatic via signal |
| Type safety | Requires `!` assertion | Proper optional typing |
| Lifecycle | AfterViewInit required | Works with effects |
| Change detection | Zone.js dependent | Zoneless compatible |

---

## Dependency Updates

### Nx Workspace Updates

```bash
# Check for Nx updates
npx nx migrate latest

# Review migrations
cat migrations.json

# Run migrations
npx nx migrate --run-migrations

# Clean up
rm migrations.json
```

### NgRx Updates

NgRx versions are tied to Angular versions:

| Angular | NgRx |
|---------|------|
| 20.x | 19.x |
| 19.x | 18.x |
| 18.x | 17.x |

```bash
# Update NgRx packages together
npm update @ngrx/store @ngrx/effects @ngrx/entity @ngrx/store-devtools
```

### RxJS Updates

```bash
# Check current version
npm list rxjs

# Update RxJS
npm update rxjs
```

**RxJS 7 to 8 Migration Notes:**

- Import paths changed: `rxjs/operators` → `rxjs`
- Some operators renamed/removed
- See official RxJS migration guide (linked in Related Documents)

### Third-Party Libraries

Check compatibility before upgrading:

```bash
# List outdated packages
npm outdated

# Check peer dependencies
npm ls @angular/core
```

---

## Breaking Changes Handling

### Identifying Breaking Changes

1. Read release notes thoroughly
2. Run `ng update` to see required changes
3. Check console warnings for deprecations
4. Review TypeScript strict mode errors

### Common Breaking Change Patterns

**API Removal**

```typescript
// BEFORE: Removed API
import { SomeDeprecatedThing } from '@angular/core';

// AFTER: Find replacement in release notes
import { ReplacementThing } from '@angular/core';
```

**Behavior Changes**

```typescript
// Document expected behavior changes in tests
it('should handle new behavior', () => {
  // Updated expectation per Angular X.Y release notes
  expect(result).toBe(newExpectedValue);
});
```

**Type Changes**

```typescript
// BEFORE: Looser typing
const value: any = service.getValue();

// AFTER: Stricter typing required
const value: SpecificType = service.getValue();
```

### Deprecation Warnings

Handle deprecation warnings proactively:

```bash
# Find deprecation warnings in build output
npx ng build 2>&1 | grep -i deprecat

# Address before they become errors
```

### Migration Testing Strategy

| Test Type | Purpose |
|-----------|---------|
| Unit tests | Verify component behavior unchanged |
| Integration tests | Verify feature workflows |
| E2E tests | Verify user journeys |
| Visual regression | Catch UI changes |

---

## Zoneless Migration

### Overview

Zoneless change detection removes the Zone.js dependency, improving performance and bundle size. As of Angular 20, zoneless is **stable and production-ready**. New applications should consider starting zoneless; existing applications can migrate incrementally.

### Preparation Checklist

Before enabling zoneless:

- [ ] All components use `OnPush` change detection
- [ ] All state managed via signals or NgRx
- [ ] No `detectChanges()` or `markForCheck()` calls
- [ ] No `setTimeout()`/`setInterval()` for CD hacks
- [ ] All async operations use signals or proper reactivity

### Enabling Zoneless

```typescript
// app.config.ts
import { provideZonelessChangeDetection } from '@angular/core';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    // ... other providers
  ]
};
```

### Removing Zone.js

After confirming zoneless works:

```typescript
// angular.json - remove zone.js polyfill
{
  "polyfills": [
    // Remove: "zone.js"
  ]
}
```

### Troubleshooting Zoneless

| Symptom | Cause | Fix |
|---------|-------|-----|
| UI not updating | Missing signal notification | Use signals for state |
| Async data not showing | Observable not triggering CD | Use `toSignal()` or async pipe |
| Third-party component broken | Library depends on Zone.js | Check for zoneless-compatible version |

---

## Migration Workflow

### Branch Strategy

```text
main
  └── upgrade/angular-21
        ├── feat/standalone-migration
        ├── feat/control-flow-migration
        └── feat/signal-migration
```

### Incremental Migration

For large applications, migrate incrementally:

1. **Phase 1:** Infrastructure (bootstrap, providers)
2. **Phase 2:** Shared libraries
3. **Phase 3:** Feature modules (one at a time)
4. **Phase 4:** Final cleanup and verification

### Migration PR Template

```markdown
## Migration Summary
- **From:** Angular X.Y / Pattern A
- **To:** Angular X.Z / Pattern B

## Changes
- [ ] Automated migration applied
- [ ] Manual fixes completed
- [ ] Tests updated
- [ ] Documentation updated

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Breaking Changes
<!-- List any breaking changes for consumers -->

## Rollback Plan
<!-- How to revert if issues found -->
```

---

## Related Documents

- [[02-Modern-Angular-Patterns]] - Target patterns for migration
- [[05-State-Management]] - State patterns including RxJS usage
- [[06-API-Integration]] - API patterns including observable usage
- [[10-CI-CD-Integration]] - CI verification during migration
- [[13-Common-Pitfalls]] - Avoid common migration mistakes
- [[Angular-Version-Changelog]] - Version history and features

**External Resources:**

- [Angular Update Guide](https://angular.dev/update-guide) - Official upgrade checklist generator
- [RxJS Migration Guide](https://rxjs.dev/deprecations) - Deprecations and migration notes

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Added inject() and view query migrations; clarified zoneless status; improved cross-references |
| 2026-01-19 | 1.1 | Full content added: version upgrades, standalone, signals, control flow |
| 2026-01-08 | 1.0 | Initial stub created |
