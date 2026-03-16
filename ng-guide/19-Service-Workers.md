---
title: "Service Workers"
created: 2026-01-14 10:00
updated: 2026-01-22 10:00
tags: [playbook, angular, work, atd-standards, service-worker, pwa, caching]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [intermediate, experienced-developers]
---

# Service Workers

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## Overview

ATD uses Angular's built-in service worker (`@angular/service-worker`) for:

- **Asset caching** - Faster load times for static resources
- **API caching** - Critical for micro-frontend architecture
- **PWA features** - Offline support and installability (select apps)

### Why Service Worker API Caching?

ATD's micro-frontend architecture means independent applications cannot share the same NgRx store instance. Service worker caching provides a shared cache layer across micro-frontends that would otherwise duplicate API calls.

---

## Setup

### Installation

Add the service worker package:

```bash
ng add @angular/service-worker
```

Or manually:

```bash
npm install @angular/service-worker
```

### Registration

Register the service worker in app config:

```typescript
// app.config.ts
import { ApplicationConfig, isDevMode } from '@angular/core';
import { provideServiceWorker } from '@angular/service-worker';

export const appConfig: ApplicationConfig = {
  providers: [
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000'
    })
  ]
};
```

> **Important:** Always disable the service worker in development (`enabled: !isDevMode()`). SW caching during development causes confusion when code changes don't appear.

### Registration Strategies

| Strategy | Behavior | Use For |
|----------|----------|---------|
| `registerWhenStable:30000` | Wait for app stable or 30s timeout | Default - doesn't block initial render |
| `registerImmediately` | Register on app bootstrap | When SW is critical to functionality |
| `registerWithDelay:5000` | Register after fixed delay | Fine-tuned control over timing |

### HTTPS Requirement

Service workers require HTTPS in production. They work on `localhost` for development, but any deployed environment must use HTTPS.

### Configuration File

Create `ngsw-config.json` in project root:

```json
{
  "$schema": "./node_modules/@angular/service-worker/config/schema.json",
  "index": "/index.html",
  "assetGroups": [],
  "dataGroups": [],
  "navigationUrls": [
    "/**",
    "!/**/*.*",
    "!/**/api/**"
  ]
}
```

The `navigationUrls` config controls which URLs are served the `index.html` for SPA routing:

- `/**` - Include all paths
- `!/**/*.*` - Exclude files with extensions (assets)
- `!/**/api/**` - Exclude API paths (let them pass through to network)

Reference in `angular.json` or `project.json`:

```json
{
  "targets": {
    "build": {
      "configurations": {
        "production": {
          "serviceWorker": true,
          "ngswConfigPath": "apps/my-app/ngsw-config.json"
        }
      }
    }
  }
}
```

---

## Asset Groups

Asset groups define how static resources are cached.

### App Shell (Prefetch)

Critical resources cached immediately on service worker install:

```json
{
  "assetGroups": [
    {
      "name": "app",
      "installMode": "prefetch",
      "updateMode": "prefetch",
      "resources": {
        "files": [
          "/favicon.ico",
          "/index.html",
          "/manifest.webmanifest",
          "/*.css",
          "/*.js"
        ]
      }
    }
  ]
}
```

### Static Assets (Lazy)

Non-critical assets cached on first request:

```json
{
  "assetGroups": [
    {
      "name": "assets",
      "installMode": "lazy",
      "updateMode": "prefetch",
      "resources": {
        "files": [
          "/assets/**",
          "/*.(png|jpg|jpeg|svg|gif|webp)",
          "/*.(woff|woff2|ttf|eot)"
        ]
      }
    }
  ]
}
```

### Install and Update Modes

**Install mode** determines when resources are first cached:

| Mode | Behavior | Use For |
|------|----------|---------|
| `prefetch` | Cache on SW install | App shell, critical JS/CSS |
| `lazy` | Cache on first request | Images, fonts, non-critical assets |

**Update mode** determines how cached resources are refreshed when a new app version is deployed:

| Mode | Behavior | Use For |
|------|----------|---------|
| `prefetch` | Immediately fetch new versions | Critical resources that must stay current |
| `lazy` | Fetch new version on next request | Non-critical assets where stale is acceptable |

---

## Data Groups (API Caching)

Data groups are essential for ATD's micro-frontend architecture. They define caching behavior for API responses.

### Basic API Caching

```json
{
  "dataGroups": [
    {
      "name": "api-cache",
      "urls": [
        "/api/**"
      ],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 100,
        "maxAge": "1h",
        "timeout": "10s"
      }
    }
  ]
}
```

### Caching Strategies

| Strategy | Behavior | Use For |
|----------|----------|---------|
| `freshness` | Network first, fall back to cache | Most API calls - prefer fresh data |
| `performance` | Cache first, fall back to network | Rarely-changing reference data |

### Strategy: Freshness (Network-First)

Attempts network request first. If it fails or times out, serves cached response:

```json
{
  "name": "api-freshness",
  "urls": ["/api/users/**", "/api/orders/**"],
  "cacheConfig": {
    "strategy": "freshness",
    "maxSize": 50,
    "maxAge": "1h",
    "timeout": "5s"
  }
}
```

### Strategy: Performance (Cache-First)

Serves from cache immediately. Updates cache in background:

```json
{
  "name": "api-performance",
  "urls": ["/api/reference/**", "/api/config/**"],
  "cacheConfig": {
    "strategy": "performance",
    "maxSize": 20,
    "maxAge": "1d"
  }
}
```

### Cache Configuration Options

| Option | Description | Example |
|--------|-------------|---------|
| `maxSize` | Maximum cached responses | `100` |
| `maxAge` | How long responses are valid | `1h`, `1d`, `30m` |
| `timeout` | Network timeout before using cache (freshness only) | `5s`, `10s` |

### Multiple Data Groups

Configure different caching for different API patterns:

```json
{
  "dataGroups": [
    {
      "name": "user-api",
      "urls": ["/api/users/**"],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 50,
        "maxAge": "30m",
        "timeout": "5s"
      }
    },
    {
      "name": "reference-data",
      "urls": ["/api/reference/**", "/api/lookup/**"],
      "cacheConfig": {
        "strategy": "performance",
        "maxSize": 100,
        "maxAge": "1d"
      }
    },
    {
      "name": "reports-api",
      "urls": ["/api/reports/**"],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 20,
        "maxAge": "1h",
        "timeout": "10s"
      }
    }
  ]
}
```

---

## Micro-Frontend Considerations

### Shared Caching Across Apps

In ATD's micro-frontend architecture:

- Each micro-frontend is an independent Angular app
- Apps cannot share NgRx store instances
- Service worker provides shared cache at browser level

```text
┌─────────────────────────────────────────────┐
│                  Browser                     │
│  ┌─────────────────────────────────────┐    │
│  │         Service Worker Cache         │    │
│  │    (Shared across micro-frontends)   │    │
│  └─────────────────────────────────────┘    │
│       ▲           ▲           ▲             │
│       │           │           │             │
│  ┌────┴───┐  ┌────┴───┐  ┌────┴───┐        │
│  │ App A  │  │ App B  │  │ App C  │        │
│  │ (NgRx) │  │ (NgRx) │  │ (NgRx) │        │
│  └────────┘  └────────┘  └────────┘        │
└─────────────────────────────────────────────┘
```

### Benefits

| Benefit | Description |
|---------|-------------|
| Reduced API calls | Shared cache prevents duplicate requests |
| Consistent data | All apps see same cached data |
| Offline support | Cache available even when network fails |
| Performance | Faster responses from cache |

### Cache Invalidation

When data changes, the service worker cache may serve stale data. Consider:

- Appropriate `maxAge` settings per API
- Using `freshness` strategy for frequently-changing data
- Short `timeout` values to prefer fresh data when available

---

## Service Worker Updates

### Automatic Updates (Default)

ATD primarily uses automatic service worker updates:

```typescript
// app.config.ts
provideServiceWorker('ngsw-worker.js', {
  enabled: true,
  registrationStrategy: 'registerWhenStable:30000'
})
```

The service worker checks for updates on navigation and periodically.

### Checking for Updates

Use `SwUpdate` service to check programmatically:

```typescript
@Injectable({ providedIn: 'root' })
export class UpdateService {
  private readonly swUpdate = inject(SwUpdate);

  checkForUpdate(): void {
    if (this.swUpdate.isEnabled) {
      this.swUpdate.checkForUpdate();
    }
  }
}
```

### Handling Available Updates

Notify users when an update is available (simplified example using `confirm()`—prefer a proper UI component for production):

```typescript
@Component({ /* ... */ })
export class AppComponent {
  private readonly swUpdate = inject(SwUpdate);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    if (this.swUpdate.isEnabled) {
      this.swUpdate.versionUpdates.pipe(
        filter(event => event.type === 'VERSION_READY'),
        takeUntilDestroyed(this.destroyRef)
      ).subscribe(() => {
        this.promptUserForUpdate();
      });
    }
  }

  private promptUserForUpdate(): void {
    if (confirm('A new version is available. Reload to update?')) {
      window.location.reload();
    }
  }
}
```

### User-Controlled Updates

For apps where users need control over update timing:

```typescript
@Component({
  template: `
    @if (updateAvailable()) {
      <div class="update-banner">
        <span>A new version is available</span>
        <button (click)="applyUpdate()">Update Now</button>
        <button (click)="dismissUpdate()">Later</button>
      </div>
    }
  `
})
export class UpdateBannerComponent {
  private readonly swUpdate = inject(SwUpdate);
  private readonly destroyRef = inject(DestroyRef);

  updateAvailable = signal(false);

  constructor() {
    if (this.swUpdate.isEnabled) {
      this.swUpdate.versionUpdates.pipe(
        filter(event => event.type === 'VERSION_READY'),
        takeUntilDestroyed(this.destroyRef)
      ).subscribe(() => {
        this.updateAvailable.set(true);
      });
    }
  }

  applyUpdate(): void {
    window.location.reload();
  }

  dismissUpdate(): void {
    this.updateAvailable.set(false);
  }
}
```

---

## PWA Features

Some ATD applications include full PWA capabilities.

### Web App Manifest

Create `manifest.webmanifest`:

```json
{
  "name": "ATD Application",
  "short_name": "ATD App",
  "theme_color": "#1976d2",
  "background_color": "#ffffff",
  "display": "standalone",
  "scope": "/",
  "start_url": "/",
  "icons": [
    {
      "src": "assets/icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "assets/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

Reference in `index.html`:

```html
<link rel="manifest" href="manifest.webmanifest">
```

### Offline Support

With proper asset and data group configuration, apps work offline:

1. App shell cached via `prefetch`
2. API responses cached via data groups
3. Users can continue working without network

### Install Prompt

Browsers show install prompt automatically when PWA criteria are met. ATD uses standard browser behavior without custom install prompts.

---

## Complete Configuration Example

```json
{
  "$schema": "./node_modules/@angular/service-worker/config/schema.json",
  "index": "/index.html",
  "assetGroups": [
    {
      "name": "app",
      "installMode": "prefetch",
      "updateMode": "prefetch",
      "resources": {
        "files": [
          "/favicon.ico",
          "/index.html",
          "/manifest.webmanifest",
          "/*.css",
          "/*.js"
        ]
      }
    },
    {
      "name": "assets",
      "installMode": "lazy",
      "updateMode": "prefetch",
      "resources": {
        "files": [
          "/assets/**",
          "/*.(png|jpg|jpeg|svg|gif|webp|woff|woff2)"
        ]
      }
    }
  ],
  "dataGroups": [
    {
      "name": "api-freshness",
      "urls": [
        "/api/users/**",
        "/api/orders/**",
        "/api/inventory/**"
      ],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 100,
        "maxAge": "1h",
        "timeout": "5s"
      }
    },
    {
      "name": "api-performance",
      "urls": [
        "/api/reference/**",
        "/api/config/**",
        "/api/lookup/**"
      ],
      "cacheConfig": {
        "strategy": "performance",
        "maxSize": 50,
        "maxAge": "1d"
      }
    }
  ]
}
```

---

## Error Handling

### Handling Update Errors

Service worker updates can fail due to network issues or corrupted caches:

```typescript
@Injectable({ providedIn: 'root' })
export class SwErrorHandler {
  private readonly swUpdate = inject(SwUpdate);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    if (this.swUpdate.isEnabled) {
      this.swUpdate.unrecoverable.pipe(
        takeUntilDestroyed(this.destroyRef)
      ).subscribe(event => {
        console.error('Service worker unrecoverable error:', event.reason);
        this.handleUnrecoverableState();
      });
    }
  }

  private handleUnrecoverableState(): void {
    if (confirm('An error occurred. Reload to recover?')) {
      window.location.reload();
    }
  }
}
```

### Common Error Scenarios

| Error | Cause | Resolution |
|-------|-------|------------|
| Unrecoverable state | Corrupted cache or hash mismatch | Clear caches, reload |
| Registration failed | HTTPS not enabled, SW file missing | Check deployment config |
| Update timeout | Slow network, large update | Increase timeout or defer |

---

## Debugging

### Chrome DevTools

1. Open DevTools → Application tab
2. Check "Service Workers" section
3. View "Cache Storage" for cached resources

### Bypass for Development

During development, enable "Bypass for network" in DevTools to skip service worker caching.

### Clear Cache

> **Warning:** This deletes ALL caches, including those from other origins or libraries. Use only for debugging, not in production code.

```typescript
// For debugging only - clears all browser caches
if (this.swUpdate.isEnabled) {
  caches.keys().then(keys => {
    keys.filter(key => key.startsWith('ngsw')).forEach(key => caches.delete(key));
  });
}
```

For a complete reset, users can also use DevTools → Application → Storage → "Clear site data".

---

## Related Documents

- [[05-State-Management]] - NgRx patterns (complement to SW caching)
- [[06-API-Integration]] - API service patterns
- [[08-Performance-Optimization]] - Performance strategies

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.1 | Added production-only enablement, registration strategies, HTTPS requirement, navigationUrls, updateMode explanation, error handling section, improved subscription cleanup with takeUntilDestroyed, added fonts to lazy assets, improved cache clear with warning |
| 2026-01-14 | 1.0 | Initial document created |
