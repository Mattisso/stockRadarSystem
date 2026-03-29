---
title: "Nx Workspace Setup"
created: 2026-01-08 10:00
updated: 2026-01-13 10:00
tags: [playbook, angular, work, atd-standards, nx, architecture]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# Nx Workspace Setup

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## Why Nx for All ATD Projects

**Nx is required for all ATD Angular projects.** This is an industry best practice that ATD has adopted for consistency and maintainability.

### Benefits ATD Has Seen

| Benefit | Description |
|---------|-------------|
| **Consistency** | Same commands and structure across all repos |
| **Consolidation** | Easier to manage and consolidate repos |
| **Future-proofing** | Standalone apps can evolve to monorepos without restructuring |
| **Affected commands** | Only test/build what changed (faster CI) |
| **Caching** | Local caching speeds rebuilds significantly |
| **Code generation** | Consistent scaffolding with generators |

### Version Policy

Nx version should match the Angular version in use. Update them in tandem when upgrading. Nx may occasionally move ahead of Angular in some of our repos, which is acceptable.

---

## Creating an Nx Workspace

### Standalone Application Setup (Typical)

Most ATD projects use the standalone preset:

```bash
npx create-nx-workspace@latest my-app --preset=angular-standalone
```

This creates a single-application workspace that can later evolve to include libraries or additional apps.

### Monorepo Setup

For projects with multiple related applications:

```bash
npx create-nx-workspace@latest my-workspace --preset=angular-monorepo
```

Use monorepo when:

- Multiple apps share significant code
- Apps are developed/deployed together
- Team wants unified versioning

---

## Project Structure

### apps/ vs libs/

| Folder | Purpose | Example |
|--------|---------|---------|
| `apps/` | Deployable applications | `apps/customer-portal/` |
| `libs/` | Shared/reusable code | `libs/ui-button/`, `libs/user-api/` |

```text
my-workspace/
├── apps/
│   ├── customer-portal/        # Main customer-facing app
│   └── admin-dashboard/        # Internal admin app
├── libs/
│   ├── ui-button/              # Button component library
│   ├── ui-modal/               # Modal component library
│   ├── ui-data-table/          # Data table component library
│   ├── user-api/               # User API services
│   ├── auth/                   # Authentication utilities
│   └── date-utils/             # Date helper functions
├── nx.json
└── package.json
```

### Library Organization Philosophy

**ATD uses flat, atomic libraries.** Each library lives at the root of `libs/` with a descriptive name.

> **Why not category folders?** Grouping libs under `shared/`, `feature/`, or `data-access/` folders creates "junk drawers" that grow unwieldy over time. A flat structure forces intentional naming and keeps libraries focused and separable.

| Principle | Description |
|-----------|-------------|
| **Flat** | Libraries sit directly under `libs/`, no category subfolders |
| **Atomic** | Each library has a single, focused purpose |
| **Separable** | Libraries can be extracted or moved independently |
| **Descriptively named** | Name conveys purpose without needing folder context |

### Library Naming Conventions

Use prefixes to indicate library type when helpful:

| Prefix | Purpose | Examples |
|--------|---------|----------|
| `ui-` | Presentational components | `ui-button`, `ui-modal`, `ui-data-table` |
| `util-` or `-utils` | Pure helper functions | `date-utils`, `util-formatting` |
| `*-api` | API/data services | `user-api`, `product-api` |
| (none) | Feature or domain libraries | `auth`, `checkout`, `user-profile` |

### When to Extract to a Library

| Scenario | Action |
|----------|--------|
| Code used in more than one place | **Must** move to library |
| Code anticipated to be reused | **Can** proactively move to library |
| Code used across multiple apps | **Must** be in library |

Developers can use their judgment to proactively extract code to libraries if they anticipate reuse, even before it's used in multiple places.

---

## Nx Commands Reference

All commands use `npx` to ensure you're using the workspace's Nx version.

### Common Development Commands

| Command | Purpose |
|---------|---------|
| `npx nx serve <app>` | Start dev server |
| `npx nx build <app>` | Build application |
| `npx nx test <project>` | Run unit tests |
| `npx nx lint <project>` | Run linting |
| `npx nx e2e <e2e-project>` | Run e2e tests |

### Affected Commands (Monorepos)

Only run tasks for projects affected by changes:

| Command | Purpose |
|---------|---------|
| `npx nx affected -t test` | Test affected projects |
| `npx nx affected -t build` | Build affected projects |
| `npx nx affected -t lint` | Lint affected projects |

These are used in CI pipelines to speed up PR validation.

### Utility Commands

| Command | Purpose |
|---------|---------|
| `npx nx graph` | Visualize dependency graph |
| `npx nx reset` | Clear cache (troubleshooting) |
| `npx nx list` | List available plugins |

#### Using nx graph

`nx graph` opens a browser-based visualization of your workspace dependencies. Use it for:

- Architecture reviews
- Debugging dependency issues
- Understanding application layout

---

## Generators

Nx generators scaffold code consistently. ATD developers use two approaches:

### Approach 1: Using Generators

```bash
# Create application
npx nx g @nx/angular:app my-app

# Create library
npx nx g @nx/angular:lib my-lib

# Create component (recommended flags)
npx nx g @nx/angular:component my-component \
  --prefix=atd \
  --changeDetection=OnPush

# Create service
npx nx g @nx/angular:service my-service
```

**Recommended flags for components:**

| Flag | Value | Purpose |
|------|-------|---------|
| `--prefix` | `atd` | ATD component prefix |
| `--changeDetection` | `OnPush` | Required change detection strategy |
| `--standalone` | `true` | Standalone component (default in Angular 17+) |
| `--style` | `scss` | SCSS styling |

**Full example with all recommended flags:**

```bash
npx nx g @nx/angular:component features/users/user-card \
  --prefix=atd \
  --changeDetection=OnPush \
  --standalone \
  --style=scss
```

### Approach 2: Copy and Modify

Some developers prefer copying an existing component and modifying it:

1. Find a recent component that's similar to what you need
2. Copy the folder to the new location
3. Rename files and update class names
4. Modify the component logic

This approach works well when:

- The new component is similar to an existing one
- You want to start with known-good patterns
- You prefer manual control over file structure

Both approaches are acceptable at ATD. The preference is to use a generator, however, choose what works best for you.

---

## Executors and Targets

### Understanding project.json

Each project has a `project.json` defining its build targets:

```json
{
  "name": "my-app",
  "targets": {
    "build": {
      "executor": "@angular-devkit/build-angular:application",
      "configurations": {
        "production": {
          "optimization": true,
          "outputHashing": "all"
        },
        "development": {
          "optimization": false
        }
      },
      "defaultConfiguration": "development"
    },
    "serve": {
      "executor": "@angular-devkit/build-angular:dev-server",
      "configurations": {
        "production": { "buildTarget": "my-app:build:production" },
        "development": { "buildTarget": "my-app:build:development" }
      }
    }
  }
}
```

ATD typically uses Nx defaults without customization.

### Environment Configurations

ATD projects typically configure these environments:

| Environment | Purpose |
|-------------|---------|
| `local` | Local development |
| `dev` | Development environment |
| `xat` | Performance and UAT testing |
| `prod` | Production |

Configure in `project.json` and corresponding `environment.*.ts` files.

---

## Caching and Performance

### Local Computation Caching

Nx automatically caches task results. When you run a task:

1. Nx computes a hash of inputs (source files, dependencies, config)
2. If the hash matches a previous run, Nx returns cached results
3. Subsequent runs of unchanged code are nearly instant

### Troubleshooting Cache Issues

The Nx daemon occasionally gets into odd states. If you see unexpected errors:

```bash
# Clear the cache
npx nx reset
```

### Disabling the Nx Daemon

In CI environments or when troubleshooting daemon issues, disable it:

```bash
# Set environment variable
export NX_DAEMON=false

# Or run with the variable inline
NX_DAEMON=false npx nx build my-app
```

ATD disables the daemon in CI pipelines for reliability.

### Nx Cloud

ATD does not currently use Nx Cloud for distributed caching. All caching is local.

---

## Integration with ATD CI/CD

ATD uses a two-phase CI/CD approach:

### Phase 1: GitHub Actions (PR Gate)

GitHub Actions runs on every PR to validate code quality:

```yaml
# Simplified example
name: PR Validation
on: [pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    env:
      NX_DAEMON: false
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'

      - run: npm ci

      - name: Lint affected
        run: npx nx affected -t lint --base=origin/main

      - name: Test affected
        run: npx nx affected -t test --base=origin/main

      - name: Build affected
        run: npx nx affected -t build --base=origin/main
```

**Key points:**

- Uses `affected` commands to only check changed code
- Blocks PR merge if lint, test, or build fails
- Prevents broken code from reaching main branch
- `NX_DAEMON=false` for reliability in CI

### Phase 2: GoCD (Build & Deploy)

After code merges to main, GoCD handles:

- Building Docker images/containers
- Deployment to environments (dev, xat, prod)
- Release management

See [[10-CI-CD-Integration]] for detailed pipeline configuration.

---

## Related Documents

- [[01-Getting-Started]] - Initial environment setup
- [[02-Modern-Angular-Patterns]] - Modern Angular patterns
- [[10-CI-CD-Integration]] - Detailed CI/CD pipeline configuration
- [[12-ATD-Conventions]] - ATD naming conventions (including `atd-` prefix)
- [[ATD-Repository-Links]] - ATD monorepo examples

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-13 | 1.2 | Revised libs structure to flat/atomic approach; removed category folders |
| 2026-01-13 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
