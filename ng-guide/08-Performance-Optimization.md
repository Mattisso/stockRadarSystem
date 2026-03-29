---
title: "Performance Optimization"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, performance, zoneless, onpush]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [intermediate, experienced-developers]
---

# Performance Optimization

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## Change Detection

> **Note:** Examples in this document use inline templates for brevity. In actual code, use external `templateUrl` per [[04-Component-Architecture#Required Configuration]].

### Zoneless Angular at ATD

**All new ATD applications must use zoneless Angular.** New applications are created without Zone.js, and any patterns that rely on zones must not appear in new code.

**Existing applications** migrate to zoneless opportunistically—there is no fixed timeline or urgency. When working in existing zoned applications:
- Write zoneless-ready code (OnPush, signals, no zone-dependent patterns)
- Migrate to zoneless during major refactors when the opportunity arises
- Don't introduce new zone dependencies

```typescript
// app.config.ts - Zoneless configuration (stable API in Angular 20.2+)
import { ApplicationConfig, provideZonelessChangeDetection } from '@angular/core';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection()
  ]
};
```

### What This Means

| Aspect | Implication |
|--------|-------------|
| Change detection | Must be explicitly triggered via signals or `ChangeDetectorRef` |
| Async operations | `setTimeout`, `setInterval`, HTTP calls don't auto-trigger CD |
| Third-party libs | Some may not work - test thoroughly |
| Performance | Significantly better - no unnecessary CD cycles |

### OnPush Is Still Required

Even in zoneless mode, OnPush remains required for all components:

```typescript
@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  // ...
})
```

OnPush + zoneless + signals provides optimal change detection performance.

### Triggering Change Detection

In zoneless mode, use signals for reactive state:

```typescript
@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div>{{ count() }}</div>
    <button (click)="increment()">+</button>
  `
})
export class CounterComponent {
  count = signal(0);

  increment(): void {
    this.count.update(n => n + 1); // Triggers CD automatically
  }
}
```

When signals aren't appropriate, manually trigger:

```typescript
export class LegacyComponent {
  private readonly cdr = inject(ChangeDetectorRef);

  onExternalEvent(): void {
    // Update state
    this.cdr.markForCheck(); // Manually trigger CD
  }
}
```

---

## Lazy Loading

### Route-Level Lazy Loading

All feature routes should use lazy loading:

```typescript
// app.routes.ts
export const routes: Routes = [
  {
    path: 'users',
    loadComponent: () => import('./features/users/user-list-page/user-list-page.component')
      .then(m => m.UserListPageComponent)
  },
  {
    path: 'settings',
    loadComponent: () => import('./features/settings/settings-page/settings-page.component')
      .then(m => m.SettingsPageComponent)
  }
];
```

### @defer Blocks

ATD encourages the use of `@defer` blocks where rational. Use them for:

- Below-the-fold content
- Conditionally shown heavy components
- Content that doesn't need immediate rendering

```typescript
@Component({
  template: `
    <header>Always visible</header>

    <main>Primary content</main>

    @defer (on viewport) {
      <atd-heavy-chart [data]="chartData()" />
    } @placeholder {
      <div class="chart-placeholder">Loading chart...</div>
    }
  `
})
```

**Defer triggers:**

| Trigger | Use Case |
|---------|----------|
| `on viewport` | Load when scrolled into view |
| `on idle` | Load when browser is idle |
| `on interaction` | Load on user interaction |
| `when condition` | Load when condition is true |

### Preloading Strategies

For better user experience, preload routes during idle time:

```typescript
// app.config.ts
import { PreloadAllModules } from '@angular/router';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes, withPreloading(PreloadAllModules))
  ]
};
```

For large applications, consider a custom preloading strategy that only preloads routes marked with `data: { preload: true }` rather than all routes.

### Server-Side Rendering

Angular supports Server-Side Rendering (SSR) with hydration for improved initial load performance and SEO. **ATD does not currently use SSR**—our applications are client-side rendered SPAs. This approach suits our internal enterprise applications where SEO is not a concern and users typically have consistent network conditions.

---

## Bundle Optimization

### Tree Shaking

Tree shaking is automatic with Angular CLI. Ensure it works effectively:

```typescript
// GOOD: Direct imports from rxjs - tree shakable
import { map, filter, debounceTime } from 'rxjs';

// AVOID: Wildcard imports
import * as Rx from 'rxjs'; // Imports entire library

// AVOID: Barrel imports of large libraries
import { something } from 'some-large-library'; // May import more than needed
```

Check library documentation for tree-shakable import patterns.

### Code Splitting

Route-based code splitting happens automatically with lazy loading. Each lazy route creates a separate chunk.

### Bundle Analysis

Analyze bundle contents when investigating size issues:

```bash
# Generate stats file
npx nx build my-app --stats-json

# Analyze with webpack-bundle-analyzer
npx webpack-bundle-analyzer dist/apps/my-app/stats.json
```

### ATD Bundle Approach

ATD does not enforce specific bundle size limits across all applications. Instead:

1. As release approaches, analyze bundle sizes
2. Determine appropriate targets for the specific application
3. Optimize as needed based on application requirements
4. Document targets in application-specific documentation

---

## Runtime Performance

### TrackBy for Lists

Always use `track` with `@for` loops for dynamic data:

```typescript
@Component({
  template: `
    @for (user of users(); track user.id) {
      <atd-user-card [user]="user" />
    }
  `
})
```

Without `track`, Angular recreates DOM elements on every change, causing:

- Poor performance with large lists
- Loss of component state
- Unnecessary re-renders

### Debouncing User Input

For search inputs and other frequent events:

```typescript
export class SearchComponent {
  private readonly searchSubject = new Subject<string>();

  searchResults = toSignal(
    this.searchSubject.pipe(
      debounceTime(300),
      distinctUntilChanged(),
      switchMap(term => this.searchService.search(term))
    )
  );

  onSearchInput(term: string): void {
    this.searchSubject.next(term);
  }
}
```

### Virtual Scrolling

Virtual scrolling with CDK is available but currently uncommon at ATD:

```typescript
// When needed for very large lists
import { ScrollingModule } from '@angular/cdk/scrolling';

@Component({
  imports: [ScrollingModule],
  template: `
    <cdk-virtual-scroll-viewport itemSize="50" class="viewport">
      <div *cdkVirtualFor="let item of items" class="item">
        {{ item.name }}
      </div>
    </cdk-virtual-scroll-viewport>
  `
})
```

> **Note:** CDK virtual scrolling requires `*cdkVirtualFor`—the `@for` control flow syntax cannot be used here because the virtualization logic is built into the directive.

Use virtual scrolling when:

- Lists exceed hundreds of items
- Users experience scroll performance issues
- Memory usage becomes problematic

### Image Optimization

Use `NgOptimizedImage` for better image performance and Core Web Vitals (LCP):

```typescript
import { NgOptimizedImage } from '@angular/common';

@Component({
  imports: [NgOptimizedImage],
  template: `
    <img ngSrc="/assets/hero.jpg" width="800" height="600" priority />
    <img ngSrc="/assets/thumbnail.jpg" width="200" height="150" />
  `
})
```

| Attribute | Purpose |
|-----------|---------|
| `ngSrc` | Enables optimizations (replaces `src`) |
| `width`/`height` | Required - prevents layout shift |
| `priority` | Disables lazy loading for above-fold images |

Benefits include automatic lazy loading, fetch priority hints, and warnings for common mistakes.

---

## Memory Management

### Why Subscription Management Matters

ATD historically encountered significant memory leak issues from unmanaged subscriptions. This is why **subscriptions in components are nearly prohibited**.

### Preferred Patterns (No Leaks)

**Option 1: Signals with selectSignal (Preferred)**

```typescript
export class UserListPageComponent {
  users = this.store.selectSignal(selectUsers);
  // No subscription, no cleanup needed
}
```

**Option 2: Async Pipe**

```typescript
@Component({
  template: `
    @for (user of users$ | async; track user.id) {
      <atd-user-card [user]="user" />
    }
  `
})
export class UserListPageComponent {
  users$ = this.store.select(selectUsers);
  // Async pipe handles subscription lifecycle
}
```

**Option 3: resource() for Async Data (Angular 20+)**

For loading async data outside of NgRx, `resource()` provides signal-based data fetching:

```typescript
export class UserDetailComponent {
  userId = input.required<string>();

  userResource = resource({
    request: () => this.userId(),
    loader: ({ request: id }) => this.userService.getById(id)
  });

  // Access in template: userResource.value(), userResource.isLoading()
}
```

This pattern handles loading states, cancellation, and cleanup automatically. See [[02-Modern-Angular-Patterns]] for details.

### When Subscription Is Unavoidable

In rare cases where you must subscribe, use `takeUntilDestroyed()`:

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

### Anti-Pattern: Unmanaged Subscriptions

```typescript
// DANGEROUS: Memory leak
export class LeakyComponent implements OnInit {
  ngOnInit(): void {
    this.someObservable$.subscribe(data => {
      this.data = data; // Leaks when component destroyed!
    });
  }
}
```

This pattern caused significant issues at ATD historically and is no longer permitted.

---

## Performance Profiling

### Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| Angular DevTools | Component tree, change detection | Chrome extension |
| Chrome Performance | Runtime profiling, flame charts | DevTools Performance tab |
| Lighthouse | Core Web Vitals, accessibility | DevTools or CLI |
| webpack-bundle-analyzer | Bundle composition | Build with stats |

### Angular DevTools

Install the Chrome extension for:

- Viewing component hierarchy
- Profiling change detection cycles
- Inspecting component state

### Lighthouse Audits

ATD runs Lighthouse independently (not systematically) to check:

- Performance metrics
- Accessibility compliance
- Best practices
- SEO (where applicable)

```bash
# CLI usage
npx lighthouse https://your-app-url --view
```

### External Performance Testing

ATD uses external third-party services for:

- Load testing
- Performance testing under realistic conditions
- Stress testing

These are coordinated separately from development workflow.

---

## ATD Performance Standards

### Application-Specific Targets

ATD does not enforce universal performance targets. Instead:

| Phase | Approach |
|-------|----------|
| Development | Focus on patterns (OnPush, signals, lazy loading) |
| Pre-release | Analyze performance metrics |
| Release | Establish application-specific targets |
| Post-release | Monitor and optimize as needed |

### Key Metrics to Track

| Metric | Description |
|--------|-------------|
| LCP | Largest Contentful Paint - main content load time |
| FID/INP | First Input Delay / Interaction to Next Paint |
| CLS | Cumulative Layout Shift - visual stability |
| Bundle size | Main bundle and lazy chunk sizes |
| Time to Interactive | When app becomes fully interactive |

### Performance Checklist

Before release, verify:

- [ ] All components use OnPush
- [ ] No unmanaged subscriptions
- [ ] Feature routes are lazy loaded
- [ ] `track` used in all `@for` loops
- [ ] No unnecessary imports bloating bundle
- [ ] Lighthouse score reviewed
- [ ] Application-specific targets documented

---

## Anti-Patterns to Avoid

### Zone-Dependent Code

```typescript
// WRONG: Relies on zone to trigger CD
setTimeout(() => {
  this.data = newData; // Won't trigger CD in zoneless
}, 1000);

// CORRECT: Use signals
setTimeout(() => {
  this.data.set(newData); // Signal triggers CD
}, 1000);
```

### Unmanaged Subscriptions

```typescript
// WRONG: Memory leak
ngOnInit() {
  this.data$.subscribe(d => this.data = d);
}

// CORRECT: Use signal or takeUntilDestroyed
data = toSignal(this.data$);
```

### Ineffective Track Expression

```typescript
// WRONG: Using $index for dynamic lists - causes DOM recreation on reorder
@for (item of items(); track $index) { ... }

// CORRECT: Track by unique identifier
@for (item of items(); track item.id) { ... }
```

> **When $index is acceptable:** Static lists that never change order or content (e.g., rendering a fixed menu). For any list that may be filtered, sorted, or updated, always track by a unique identifier.

### Eager Loading Everything

```typescript
// WRONG: All routes loaded upfront
{ path: 'users', component: UserListPageComponent }

// CORRECT: Lazy load
{ path: 'users', loadComponent: () => import('./...').then(m => m.UserListPageComponent) }
```

---

## Related Documents

- [[02-Modern-Angular-Patterns]] - Signals and zoneless patterns
- [[04-Component-Architecture]] - OnPush components
- [[13-Common-Pitfalls]] - Performance anti-patterns
- [[17-Production-Support]] - Performance incident response

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.4 | Clarified zoneless policy: required for new projects, opportunistic migration for existing (no fixed timeline) |
| 2026-01-21 | 1.3 | Added NgOptimizedImage; added resource() API; added SSR note; noted cdkVirtualFor requirement; improved track explanation; fixed RxJS imports; removed lodash example |
| 2026-01-19 | 1.2 | Updated zoneless API from experimental to stable (provideZonelessChangeDetection) |
| 2026-01-14 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
