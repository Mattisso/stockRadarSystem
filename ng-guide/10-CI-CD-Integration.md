---
title: "CI/CD Integration"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, ci-cd, devops]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [experienced-developers, tech-leads]
---

# CI/CD Integration

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## ATD CI/CD Architecture

ATD uses a two-phase CI/CD approach with clear separation of concerns:

| Phase | Tool | Purpose |
|-------|------|---------|
| **Pre-Merge** | GitHub Actions | Quality gate - prevent bad code from entering main |
| **Post-Merge** | GoCD | Build & deployment - controlled release management |

### Architecture Philosophy

```text
┌─────────────────────────────────────────────────────────────────┐
│                         DEVELOPER                                │
│                             │                                    │
│                             ▼                                    │
│                      Create PR to main                           │
│                             │                                    │
├─────────────────────────────┼────────────────────────────────────┤
│   GITHUB ACTIONS            │                                    │
│   (Pre-Merge Gate)          ▼                                    │
│                    ┌─────────────────┐                           │
│                    │  Lint Affected  │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │  Test Affected  │◄── 90% coverage required  │
│                    └────────┬────────┘                           │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │ Build Affected  │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│                    All pass? ──► Merge to main                   │
├─────────────────────────────┼────────────────────────────────────┤
│   GOCD                      │                                    │
│   (Post-Merge)              ▼                                    │
│                    ┌─────────────────┐                           │
│                    │  Create Tag     │◄── Required for deploy    │
│                    └────────┬────────┘                           │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │ Build Container │──► Artifact Registry      │
│                    └────────┬────────┘                           │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │ Deploy to Env   │──► dev / xat / prod       │
│                    └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

| Principle | Description |
|-----------|-------------|
| **Decoupled testing and deployment** | Code changes trigger tests, but deployment timing is independent |
| **All affected tests must pass** | Regardless of deployment plans, changed code must be validated |
| **Tag-based deployment** | Only tagged versions can be deployed |
| **Flexible environment targeting** | No enforced dev → qa → prod progression |

---

## GitHub Actions Workflows

### PR Validation

The primary GitHub Actions workflow validates PRs before merge:

```yaml
name: PR Validation
on:
  pull_request:
    branches: [main]

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

      - name: Install dependencies
        run: npm ci

      - name: Lint affected
        run: npx nx affected -t lint --base=origin/main

      - name: Test affected
        run: npx nx affected -t test --base=origin/main --coverage

      - name: Build affected
        run: npx nx affected -t build --base=origin/main
```

> **Future Enhancement:** We are exploring running lint, test, and build as parallel jobs rather than sequential steps. Since these tasks are independent, parallelization could reduce total PR validation time.

### Critical Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `fetch-depth: 0` | Full history | Required for `nx affected` to compare branches |
| `NX_DAEMON: false` | Disabled | Prevents daemon issues in ephemeral CI runners |
| `node-version: '22'` | Node 22 | Current ATD standard |
| `cache: 'npm'` | npm cache | Speeds up dependency installation |

### Test Execution

Tests run via `nx affected` to only test changed projects:

```yaml
- name: Test affected
  run: npx nx affected -t test --base=origin/main --coverage
```

Coverage thresholds are enforced by the test runner (Jest or Vitest). Tests fail automatically if coverage falls below the configured threshold—no separate CI step is needed:

```typescript
// jest.config.ts
export default {
  coverageThreshold: {
    global: {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    }
  }
};
```

### Lint and Format Checks

```yaml
- name: Lint affected
  run: npx nx affected -t lint --base=origin/main
```

ESLint rules are defined per-project and enforced on all affected code.

### Nx Affected Commands

The `affected` command uses Nx's dependency graph to determine what changed:

```bash
# Test only projects affected by changes
npx nx affected -t test --base=origin/main

# Lint only affected projects
npx nx affected -t lint --base=origin/main

# Build only affected projects
npx nx affected -t build --base=origin/main
```

**How it works:**

1. Nx analyzes the dependency graph of the workspace
2. Compares current branch to base (main)
3. Identifies which projects' source files changed
4. Includes dependent projects in the affected set
5. Runs tasks only on affected projects

This provides significant CI time savings in monorepos.

> **Note:** The `--head` flag is not needed in CI because GitHub Actions checks out the PR branch, making it the implicit head.

### Branch Protection Rules

GitHub branch protection enforces CI requirements:

| Rule | Setting | Purpose |
|------|---------|---------|
| Require status checks | Enabled | PR validation must pass before merge |
| Require branches up to date | Enabled | PR must be current with main |
| Require pull request reviews | 1 reviewer | Code review required |
| Restrict push to main | Enabled | No direct commits to main |

**Merge queue (future):** Merge protection rules are configured but currently disabled. When enabled, they will require PRs to pass through a merge queue, preventing broken builds from concurrent merges.

---

## GoCD Integration

### Build Pipeline

GoCD handles post-merge builds and deployments.

**Trigger:** Version tag creation in GitHub

```text
Tag Created (v1.2.3)
       │
       ▼
┌─────────────────┐
│   Build Stage   │
│                 │
│ • Checkout tag  │
│ • npm ci        │
│ • nx build app  │
│ • Docker build  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Push Artifact  │
│                 │
│ • Tag image     │
│ • Push to GAR   │
└─────────────────┘
```

**Key characteristics:**

| Characteristic | Description |
|----------------|-------------|
| Automatic build | All tags automatically built |
| No user initiation | Tag creation triggers build |
| Artifact storage | Google Artifact Registry (GAR) |
| Build ≠ Deploy | Building doesn't trigger deployment |

### Deployment Pipeline

Deployment is separate from building and user-initiated:

```text
┌─────────────────────────────────────────┐
│         Deployment Pipeline              │
│                                         │
│  1. Select version tag (from dropdown)  │
│  2. Select target environment           │
│  3. Trigger deployment                  │
│                                         │
│  Available tags: v1.2.3, v1.2.2, v1.2.1 │
│  Target envs: dev, xat, prod            │
└─────────────────────────────────────────┘
```

**Deployment rules:**

- **Must deploy from tag**: Cannot deploy arbitrary commits
- **No enforced progression**: Can deploy any tag to any environment
- **User-initiated**: Deployment timing is a deliberate decision

### Environment Management

ATD environments:

| Environment | Purpose | When to Deploy |
|-------------|---------|----------------|
| `local` | Local development | N/A (not deployed) |
| `dev` | Development testing | Frequent, after feature completion |
| `xat` | Performance/UAT testing | Before production release |
| `prod` | Production | After xat validation |

Environment configurations in `project.json`:

```json
{
  "targets": {
    "build": {
      "configurations": {
        "local": { "fileReplacements": [/*...*/] },
        "dev": { "fileReplacements": [/*...*/] },
        "xat": { "fileReplacements": [/*...*/] },
        "production": { "fileReplacements": [/*...*/], "optimization": true }
      }
    }
  }
}
```

---

## Nx in CI

### Affected Testing

The `affected` command dramatically reduces CI time:

```bash
# Compare against main branch
npx nx affected -t test --base=origin/main

# In GitHub Actions, main is automatically used as base
# for pull_request events
```

**Example impact:**

| Scenario | Without Affected | With Affected |
|----------|------------------|---------------|
| Change 1 lib in 20-app monorepo | Test all 20 apps | Test only dependent apps |
| Change shared UI component | ~15 min | ~3 min |
| Change isolated feature | ~15 min | ~1 min |

### Caching in CI

ATD uses local caching only (no Nx Cloud):

```yaml
env:
  NX_DAEMON: false
  # No NX_CLOUD_ACCESS_TOKEN - not using remote cache
```

**Caching behavior in CI:**

- Fresh clone each run (no persistent cache)
- Within-run caching still helps (multiple affected targets)
- Consider adding npm cache for faster installs

### Distributed Task Execution

ATD does not currently use Nx Cloud's distributed task execution (DTE). All CI tasks run on a single runner.

---

## Environment Configuration

### Environment Variables

Standard CI environment variables:

```yaml
env:
  NX_DAEMON: false          # Disable daemon in CI
  NODE_ENV: production      # Production-like builds
  # CI: true is set automatically by GitHub Actions
```

### Secrets Management

Secrets are managed in GitHub Actions secrets:

```yaml
steps:
  - name: Configure GCP
    uses: google-github-actions/auth@v2
    with:
      credentials_json: ${{ secrets.GCP_SA_KEY }}
```

**Security practices:**

- Never commit secrets to repository
- Use GitHub Actions secrets for CI
- Use GoCD secure variables for deployment secrets
- Rotate credentials periodically

### Configuration Files

Each environment has corresponding configuration:

```text
src/
├── environments/
│   ├── environment.ts           # Local development
│   ├── environment.dev.ts       # Dev environment
│   ├── environment.xat.ts       # XAT environment
│   └── environment.prod.ts      # Production
```

Example environment file:

```typescript
// environment.dev.ts
export const environment = {
  production: false,
  apiUrl: 'https://api.dev.atd.com',
  authConfig: {
    issuer: 'https://atd-dev.okta.com',
    clientId: 'dev-client-id'
  }
};
```

---

## Deployment Patterns

### Tag-Based Deployment

All deployments originate from version tags:

```bash
# Create version tag (triggers automatic build)
git tag v1.2.3
git push origin v1.2.3

# Build happens automatically in GoCD
# Deploy when ready via GoCD UI
```

**Tag naming convention:**

| Format | Example | Use |
|--------|---------|-----|
| `v{major}.{minor}.{patch}` | v1.2.3 | Standard releases |
| `v{major}.{minor}.{patch}-rc.{n}` | v1.2.3-rc.1 | Release candidates |
| `v{major}.{minor}.{patch}-hotfix.{n}` | v1.2.3-hotfix.1 | Hotfixes |

### Environment Promotion

ATD uses flexible promotion without enforced sequence:

```text
Tag v1.2.3 can be deployed to:

  ┌─────┐
  │ dev │  ◄── Can deploy anytime
  └─────┘

  ┌─────┐
  │ xat │  ◄── Can deploy without dev first
  └─────┘

  ┌─────┐
  │prod │  ◄── Can deploy without xat first (emergency)
  └─────┘
```

**Best practice:** Follow dev → xat → prod progression for standard releases, but flexibility exists for emergencies.

**Track deployments externally:** Which tags are deployed to which environments is tracked outside the pipeline (release notes, deployment log, etc.).

### Rollback Procedures

To rollback, deploy a previous known-good tag:

```text
Current state: v1.2.3 in prod (has bug)
Action: Deploy v1.2.2 to prod

1. In GoCD deployment pipeline
2. Select v1.2.2 from tag dropdown
3. Select prod environment
4. Trigger deployment
```

For detailed incident response, see [[17-Production-Support]].

### Deployment Verification (Planned)

ATD does not currently have automated deployment verification. This is a planned enhancement:

| Phase | Current State | Future State |
|-------|---------------|--------------|
| Post-deployment | Manual verification | Automated smoke tests |
| Pre-production gate | Manual UAT sign-off | E2E tests on xat required before prod promotion |

**Planned workflow:**

```text
Deploy to xat
     │
     ▼
┌─────────────────┐
│ Run E2E suite   │◄── Automated gate
└────────┬────────┘
         │
    Pass? ──► Allowed to deploy to prod
```

Until automated verification is implemented, rely on manual testing and stakeholder sign-off before production deployments.

---

## Branching Strategy

### Trunk-Based Development (Recommended)

ATD is moving toward trunk-based development:

```text
                    main
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
feature/xyz      feature/abc      fix/bug-123
    │                 │                 │
    └─────────────────┴─────────────────┘
                      │
                      ▼
              Tags: v1.2.3, v1.2.4
```

**Benefits:**

- Simpler mental model
- No branch drift
- Natural fit with tag-based deployment
- Reduced merge conflicts

> **Legacy note:** Some older repositories still use environment branches (`main → dev → qa → prod`). New projects should use trunk-based development.

---

## Dependency Management

### Dependabot

ATD uses Dependabot for automated dependency updates:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      angular:
        patterns:
          - "@angular/*"
          - "@angular-devkit/*"
      nx:
        patterns:
          - "@nx/*"
          - "nx"
```

**Handling Dependabot PRs:**

| PR Type | Action |
|---------|--------|
| Patch updates | Review and merge if CI passes |
| Minor updates | Review changelog, test locally if significant |
| Major updates | Coordinate with team, may require migration work |
| Security updates | Prioritize review and merge |

Dependabot PRs go through the same CI validation as regular PRs—all affected tests must pass.

---

## CI Checklist

### PR Validation Must Pass

| Check | Requirement |
|-------|-------------|
| Lint affected | All lint rules pass |
| Test affected | All tests pass |
| Coverage | 90%+ threshold |
| Build affected | Builds successfully |

### Before Creating Tag

- [ ] All PR checks passed on main
- [ ] Feature complete and tested
- [ ] Release notes prepared
- [ ] Team notified of upcoming release

### Before Production Deployment

- [ ] Validated in xat environment
- [ ] Stakeholder sign-off obtained
- [ ] Rollback plan confirmed (previous tag identified)
- [ ] Monitoring dashboards reviewed

---

## Related Documents

- [[03-Nx-Workspace-Setup]] - Nx workspace configuration and commands
- [[07-Testing-Strategies]] - Test coverage requirements
- [[17-Production-Support]] - Incident response and hotfixes
- [[18-Application-Lifecycle]] - Release management and maintenance
- [[ATD-Online-Monorepo-CICD-Pipeline]] - Detailed pipeline architecture

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Added branch protection rules, deployment verification (planned), Dependabot section; clarified coverage enforcement; noted parallel jobs exploration |
| 2026-01-19 | 1.1 | Full content added: GitHub Actions, GoCD, Nx CI integration |
| 2026-01-08 | 1.0 | Initial stub created |
