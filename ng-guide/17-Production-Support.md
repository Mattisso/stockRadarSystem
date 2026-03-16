---
title: "Production Support"
created: 2026-01-12 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, production, troubleshooting, debugging]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [experienced-developers, tech-leads]
---

# Production Support

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## Overview

This document provides troubleshooting techniques for Angular applications running in production. ATD Angular apps run in Kubernetes pods fronted by Nginx, which handles health checks and static asset serving.

---

## Browser DevTools Debugging

### Console Errors

**First step for any issue:** Open browser DevTools (F12) and check the Console tab.

| Error Pattern | Likely Cause | Investigation |
|---------------|--------------|---------------|
| `TypeError: Cannot read property 'x' of undefined` | Null/undefined data | Check API response, add null checks |
| `ChunkLoadError` | Stale cached JS after deploy | Hard refresh, clear cache |
| `ExpressionChangedAfterItHasBeenCheckedError` | Change detection timing | See dedicated section below |
| `NullInjectorError: No provider for X` | Missing provider | Check component imports, app.config providers |
| `NG0100` - `NG0999` | Angular-specific errors | Search Angular error guide with code |

### Network Tab Investigation

**Check for failed requests:**

1. Open Network tab, filter by `Fetch/XHR`
2. Look for red (failed) requests
3. Click request → Headers tab for URL and status
4. Click Response tab to see error body
5. Check Timing tab for slow responses

**Common network issues:**

| Status | Meaning | Check |
|--------|---------|-------|
| 401 | Unauthorized | Token expired? Check auth interceptor |
| 403 | Forbidden | User permissions? API authorization |
| 404 | Not Found | Correct URL? API deployed? |
| 500 | Server Error | Backend logs |
| 502/504 | Gateway Error | Nginx/K8s pod health, backend availability |
| CORS | Cross-origin blocked | API gateway config, allowed origins |

### Application Tab

**Storage issues:**

- LocalStorage/SessionStorage: Check for corrupted or missing auth tokens
- Clear site data: Application → Storage → Clear site data

---

## Angular-Specific Debugging

### ExpressionChangedAfterItHasBeenCheckedError

This error means a value changed after Angular checked it (development mode only).

**Common causes and fixes:**

```typescript
// PROBLEM: Changing value in ngAfterViewInit
ngAfterViewInit(): void {
  this.showContent = true; // Error!
}

// FIX 1: Use signals (preferred)
showContent = signal(false);
constructor() {
  afterNextRender(() => {
    this.showContent.set(true);
  });
}

// FIX 2: Use setTimeout (not ideal)
ngAfterViewInit(): void {
  setTimeout(() => this.showContent = true);
}
```

### Change Detection Issues

**UI not updating when data changes:**

1. Verify component uses `OnPush` correctly
2. Check if input reference changed (not just mutated)
3. For signals: ensure calling as function `{{ mySignal() }}`
4. For observables: ensure using `async` pipe or `toSignal()`

**Debug change detection:**

```typescript
// Add to component temporarily
constructor(private cdr: ChangeDetectorRef) {
  // Force detection to confirm data issue vs CD issue
  setInterval(() => this.cdr.detectChanges(), 1000);
}
```

### Angular DevTools

Install the Angular DevTools browser extension for:

- **Component tree:** Inspect component hierarchy and properties
- **Profiler:** Record and analyze change detection cycles
- **Signal debugging:** View signal values and dependencies

**Using the profiler:**

1. Open Angular DevTools → Profiler tab
2. Click Record
3. Perform the action causing issues
4. Stop recording
5. Look for components with excessive change detection

### Router Debugging

**Navigation not working:**

```typescript
// Enable router tracing temporarily
provideRouter(routes, withDebugTracing())
```

**Guard blocking navigation:**

1. Add console.log to guard
2. Check guard return value
3. Verify async guards complete (don't hang)

```typescript
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  console.log('Guard check, authenticated:', auth.isAuthenticated());
  return auth.isAuthenticated();
};
```

---

## NgRx Debugging

### Redux DevTools

Install Redux DevTools browser extension to:

- View action history
- Inspect state at any point
- Time-travel through actions
- Export/import state for reproduction

### State Not Updating

1. **Action dispatched?** Check Redux DevTools action log
2. **Reducer handling action?** Check state diff after action
3. **Selector correct?** Test selector with known state
4. **Component subscribing?** Verify `selectSignal()` or `select()` usage

### Effect Not Triggering

```typescript
// Debug with tap
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    tap(action => console.log('All actions:', action)),
    ofType(loadUsers),
    tap(() => console.log('loadUsers action matched')),
    switchMap(() =>
      this.api.getUsers().pipe(
        tap(users => console.log('API returned:', users)),
        map(users => loadUsersSuccess({ users })),
        catchError(error => {
          console.error('API error:', error);
          return of(loadUsersFailure({ error: error.message }));
        })
      )
    )
  )
);
```

**Common effect issues:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| Never triggers | Wrong action type in `ofType()` | Check action import |
| Triggers once then stops | Unhandled error killed stream | Add `catchError` inside `switchMap` |
| Triggers but no state change | Not returning action | Check `map()` returns action |
| Multiple triggers | Using `mergeMap` instead of `switchMap` | Use appropriate operator |

---

## Signal Debugging

### Signal Not Updating UI

1. **Template syntax:** Must call as function `{{ count() }}` not `{{ count }}`
2. **Signal being set:** Add `effect(() => console.log(mySignal()))` to trace
3. **Computed dependencies:** All dependencies must be signals

```typescript
// Debug signal changes
effect(() => {
  console.log('users signal changed:', this.users());
});
```

### Computed Not Recomputing

```typescript
// WRONG: Non-signal dependency not tracked
fullName = computed(() => {
  return this.firstName + ' ' + this.lastName; // Plain properties!
});

// CORRECT: Signal dependencies
firstName = signal('');
lastName = signal('');
fullName = computed(() => this.firstName() + ' ' + this.lastName());
```

### toSignal() Issues

```typescript
// PROBLEM: No initial value, returns undefined initially
const data = toSignal(this.http.get('/api/data'));
// data() is undefined until HTTP completes

// FIX: Provide initial value
const data = toSignal(this.http.get('/api/data'), { initialValue: [] });
```

---

## Performance Debugging

### Slow Initial Load

1. **Check bundle size:**

   ```bash
   npx nx build my-app --stats-json
   npx webpack-bundle-analyzer dist/apps/my-app/stats.json
   ```

2. **Network waterfall:** DevTools → Network → record page load
3. **Lighthouse audit:** DevTools → Lighthouse → Generate report

### Slow Runtime Performance

1. **Record performance:** DevTools → Performance → Record during slow action
2. **Look for:**
   - Long tasks (red bars, > 50ms)
   - Excessive scripting time
   - Layout thrashing (alternating purple/green bars)

### Memory Leaks

**Symptoms:** App gets slower over time, memory usage grows

**Debug steps:**

1. DevTools → Memory tab
2. Take heap snapshot (baseline)
3. Perform suspected leaking action multiple times
4. Take another snapshot
5. Compare: look for growing object counts

**Common Angular memory leaks:**

| Leak Source | Fix |
|-------------|-----|
| Unsubscribed observables | Use `takeUntilDestroyed()` or `async` pipe |
| Event listeners not removed | Use `DestroyRef` and cleanup |
| Detached DOM nodes | Check for hidden elements holding references |
| Intervals/timeouts | Clear in `ngOnDestroy` or use `takeUntilDestroyed()` |

```typescript
// Proper cleanup with takeUntilDestroyed
export class MyComponent {
  private destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.someService.data$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(data => this.handleData(data));
  }
}
```

---

## Common Production Issues

### ChunkLoadError After Deployment

**Cause:** Browser has cached old JS that references chunks that no longer exist.

**Symptoms:**

- `Loading chunk X failed`
- App partially loads then breaks
- Only affects users who had app open before deploy

**Solutions:**

1. User: Hard refresh (Ctrl+Shift+R)
2. Handle in app:

```typescript
// In global error handler
if (error.message?.includes('Loading chunk')) {
  window.location.reload();
}
```

### Authentication Issues

| Issue | Debug Steps |
|-------|-------------|
| Token expired, user stuck | Check sessionStorage for token, verify expiry time |
| Silent renewal failing | Network tab → look for token refresh calls |
| CORS on auth endpoints | Check Okta/IdP allowed origins config |
| Redirect loop | Console log in auth callback, check state parameter |

### Hydration Errors (SSR)

**Cause:** Server-rendered HTML doesn't match client render.

**Debug:**

1. Check console for hydration mismatch details
2. Look for browser-only APIs used during SSR (`window`, `document`)
3. Check for non-deterministic rendering (dates, random IDs)

```typescript
// Fix: Skip browser-only code during SSR
import { isPlatformBrowser } from '@angular/common';
import { PLATFORM_ID, inject } from '@angular/core';

const isBrowser = isPlatformBrowser(inject(PLATFORM_ID));
if (isBrowser) {
  // Browser-only code
}
```

---

## Kubernetes/Nginx Context

ATD Angular apps run as static files served by Nginx in Kubernetes pods.

### Debugging Nginx Issues

**Check Nginx logs:**

```bash
kubectl logs <pod-name> -c nginx
```

**Common Nginx issues:**

| Symptom | Likely Cause | Check |
|---------|--------------|-------|
| 404 on route refresh | Missing try_files | Nginx config needs `try_files $uri $uri/ /index.html` |
| 502 Bad Gateway | Backend unavailable | Backend pod health, service endpoints |
| Slow responses | Nginx buffering | Check proxy_buffer settings |
| Stale content | Aggressive caching | Cache-control headers, CDN purge |

### Pod Troubleshooting

```bash
# Check pod status
kubectl get pods -l app=my-angular-app

# View pod logs
kubectl logs <pod-name>

# Exec into pod for debugging
kubectl exec -it <pod-name> -- /bin/sh

# Check if app files exist
ls /usr/share/nginx/html/
```

---

## Related Documents

- [[08-Performance-Optimization]] - Performance patterns and profiling
- [[10-CI-CD-Integration]] - Deployment pipelines
- [[13-Common-Pitfalls]] - Known issues and anti-patterns

**External Resources:**

- [Angular DevTools](https://angular.dev/tools/devtools) - Browser extension for debugging
- [Chrome DevTools](https://developer.chrome.com/docs/devtools/) - Browser debugging guide

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 2.0 | Complete rewrite: focused on troubleshooting techniques, removed process content |
| 2026-01-19 | 1.2 | Corrections: clarified memory leak terminology |
| 2026-01-19 | 1.1 | Full content added |
| 2026-01-12 | 1.0 | Initial stub created |
