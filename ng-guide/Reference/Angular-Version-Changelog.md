---
title: "Angular Version Changelog"
created: 2026-01-08 10:00
updated: 2026-01-22 10:00
tags: [playbook, angular, work, atd-standards, changelog, reference]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
---

# Angular Version Changelog

**Back to:** [[00-Playbook-Index|Playbook Index]]

This document tracks Angular version releases and their impact on ATD applications.

---

## Latest Version: Angular 21.x

### Angular 21.0 (November 2025)

**Key Features:**

- Signal Forms - reimagined form API using Signals instead of RxJS
- Zoneless change detection now default for new projects
- Vitest as default test runner (replacing Karma)
- Angular ARIA accessibility library (developer preview)
- MCP Server for AI-assisted development
- New mascot "Angie"

**Breaking Changes:**

- Zoneless is now the default for new projects
- Karma/Jasmine replaced by Vitest

**Official Release Notes:** [Announcing Angular v21](https://blog.angular.dev/announcing-angular-v21-57946c34f14b)

---

## Upcoming: Angular 22.x (Expected May 2026)

**Expected Features:**
<!-- To be updated when released -->

---

## Playbook Version: Angular 20.x

This playbook is currently written for Angular 20.x. See [[14-Migration-Guides]] for upgrade guidance.

### Angular 20.0 (May 2025)

**Key Features:**

- Stabilized APIs: effect(), linkedSignal(), toSignal()
- Zoneless change detection (developer preview)
- Incremental hydration stable
- Template hot module replacement by default
- Vitest experimental integration

**Breaking Changes:**

- Node.js 18 no longer supported (requires 20.11.1+)

**Official Release Notes:** [Announcing Angular v20](https://blog.angular.dev/announcing-angular-v20-b5c9c06cf301)

---

## Previous Versions

### Angular 19.x

**Key Features:**

- Standalone components as default
- Signals API stabilized
- New control flow syntax (@if, @for, @switch) as default
- inject() function recommended over constructor injection
- Improved hydration for SSR

### Angular 18.x

**Key Features:**

- Stable signals
- Control flow syntax introduced
- Zoneless applications preview

### Angular 17.x

**Key Features:**

- New control flow syntax (@if, @for, @switch)
- Deferrable views (@defer)
- Built-in SSR improvements

---

## ATD Version Support Policy

| Angular Version | ATD Support Status | End of Support |
|-----------------|-------------------|----------------|
| 21.x | Latest | Active |
| 20.x | Current (Playbook) | Active |
| 19.x | Supported | TBD |
| < 19 | Unsupported | Migrate ASAP |

---

## Migration Resources

- [[14-Migration-Guides]] - Step-by-step migration guides
- [Angular Update Guide](https://angular.dev/update-guide) - Official migration tool

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.2 | Added Angular 21.x (Nov 2025) with accurate features, updated Angular 20.x details, reorganized structure |
| 2026-01-22 | 1.1 | Updated to Angular 20.x as current version, added Angular 19.x to previous versions |
| 2026-01-08 | 1.0 | Initial changelog created |
