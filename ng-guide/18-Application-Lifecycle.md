---
title: "Application Lifecycle Management"
created: 2026-01-12 10:00
updated: 2026-01-22 10:00
tags: [playbook, angular, work, atd-standards, lifecycle, operations, maintenance]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.0"
audience: [tech-leads, experienced-developers, devops]
---

# Application Lifecycle Management

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## Overview

This document covers the operational lifecycle of Angular applications at ATD, from release management through maintenance, upgrades, and eventual end-of-life procedures.

---

## Release Management

### Release Cadence

ATD Angular applications follow a regular release cadence:

| Release Type | Frequency | Content |
|--------------|-----------|---------|
| **Regular release** | Every 2 weeks | Features, bug fixes |
| **Hotfix** | As needed | Critical fixes only |
| **Major release** | Quarterly | Breaking changes, major features |

### Release Planning

**Pre-Release Checklist:**

- [ ] All features complete and tested
- [ ] All PRs merged to main
- [ ] Release notes drafted
- [ ] Stakeholders notified
- [ ] QA sign-off obtained
- [ ] Deployment window confirmed

### Version Numbering

ATD uses Semantic Versioning (SemVer):

```text
MAJOR.MINOR.PATCH[-PRERELEASE]

Examples:
1.0.0          - Initial release
1.1.0          - New features, backward compatible
1.1.1          - Bug fixes only
1.2.0-rc.1     - Release candidate
2.0.0          - Breaking changes
1.2.3-hotfix.1 - Emergency hotfix (increment hotfix number for subsequent fixes)
```

**Hotfix versioning:** When multiple hotfixes are needed before the next regular release, increment the hotfix number: `1.2.3-hotfix.1` → `1.2.3-hotfix.2`. Once a regular release occurs, the hotfix suffix is dropped and the PATCH version is incremented normally.

**When to increment:**

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Breaking API change | MAJOR | Remove/rename public component |
| New feature | MINOR | Add new page, component |
| Bug fix | PATCH | Fix display issue |
| Hotfix | PATCH + suffix | Critical production fix |

### Release Notes

**Release notes template:**

```markdown
# Release v1.2.0 - 2026-01-19

## New Features
- Added user profile page (#123)
- Implemented order history export (#124)

## Bug Fixes
- Fixed cart total calculation (#125)
- Resolved login redirect issue (#126)

## Breaking Changes
- None

## Upgrade Notes
- Run `npm install` to update dependencies

## Known Issues
- None
```

---

## Feature Flags

### When to Use Feature Flags

| Scenario | Use Flag? | Reason |
|----------|-----------|--------|
| Major UI change | Yes | Gradual rollout, easy rollback |
| A/B testing | Yes | Required for experiment |
| Unfinished feature | Yes | Ship code, enable later |
| Bug fix | No | Just fix and deploy |
| Minor change | No | Overhead not worth it |

### Feature Flag Implementation

**Environment-based flags:**

```typescript
// environment.ts
export const environment = {
  production: false,
  featureFlags: {
    newDashboard: true,
    betaCheckout: false,
    darkMode: true
  }
};

// feature-flag.service.ts
@Injectable({ providedIn: 'root' })
export class FeatureFlagService {
  // Signal allows reactive updates when flags are fetched from a backend service
  private readonly flags = signal(environment.featureFlags);

  isEnabled(flag: keyof typeof environment.featureFlags): boolean {
    return this.flags()[flag] ?? false;
  }

  // Future: Load flags from backend service
  // loadFlags(): void {
  //   this.http.get<FeatureFlags>('/api/feature-flags')
  //     .subscribe(flags => this.flags.set(flags));
  // }
}

// Usage in component
@Component({
  template: `
    @if (featureFlags.isEnabled('newDashboard')) {
      <atd-new-dashboard />
    } @else {
      <atd-legacy-dashboard />
    }
  `
})
export class DashboardPageComponent {
  featureFlags = inject(FeatureFlagService);
}
```

**Preferred: Service-based with @if (modern control flow):**

```typescript
// Usage in component template (preferred)
@if (featureFlags.isEnabled('newDashboard')) {
  <div>New dashboard content</div>
}
```

**Alternative: Directive-based (legacy structural directive):**

If a directive pattern is needed (e.g., for library compatibility), a structural directive can be used. Note that this uses legacy `*directive` syntax since structural directives cannot use `@if`:

```typescript
// feature-flag.directive.ts
@Directive({
  selector: '[atdFeatureFlag]',
  standalone: true
})
export class FeatureFlagDirective {
  private readonly featureFlagService = inject(FeatureFlagService);
  private readonly templateRef = inject(TemplateRef<unknown>);
  private readonly viewContainer = inject(ViewContainerRef);

  @Input() set atdFeatureFlag(flag: keyof typeof environment.featureFlags) {
    if (this.featureFlagService.isEnabled(flag)) {
      this.viewContainer.createEmbeddedView(this.templateRef);
    } else {
      this.viewContainer.clear();
    }
  }
}

// Usage in template (structural directive syntax required for directives)
<div *atdFeatureFlag="'newDashboard'">
  New dashboard content
</div>
```

> **Note:** Prefer the service-based `@if` approach for new code. Use the directive only when the structural directive pattern provides specific benefits.

### Feature Flag Lifecycle

```text
1. Create flag (disabled in prod)
2. Develop feature behind flag
3. Enable in dev/XAT for testing
4. Gradual rollout to production (%)
5. Full rollout (100%)
6. Remove flag and dead code
```

### Feature Flag Governance

**Flag cleanup rules:**

| Flag Age | Action |
|----------|--------|
| > 30 days at 100% | Remove flag, keep feature |
| > 90 days at 0% | Remove flag and dead code |
| > 180 days | Mandatory review |

**Documentation requirements:**

- Each flag must have an owner
- Each flag must have a planned removal date
- Each flag must be tracked in Jira

---

## Application Maintenance

### Regular Maintenance Tasks

| Task | Frequency | Owner |
|------|-----------|-------|
| Dependency updates | Weekly | Dev team |
| Security audit | Monthly | Security + Dev |
| Performance review | Monthly | Dev team |
| Code quality review | Quarterly | Tech lead |

### Dependency Management

**Automated dependency updates:**

Configure Dependabot for automated PRs (see [[10-CI-CD-Integration]] for pipeline setup):

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "06:00"
    groups:
      angular:
        patterns:
          - "@angular/*"
        update-types:
          - "minor"
          - "patch"
      ngrx:
        patterns:
          - "@ngrx/*"
        update-types:
          - "minor"
          - "patch"
    open-pull-requests-limit: 10
```

**Manual update process:**

Use `npm` for package management and `nx` for build/test tasks (see [[03-Nx-Workspace-Setup]]):

```bash
# Check for outdated packages
npm outdated

# Update minor/patch versions
npm update

# Update major versions (review breaking changes first)
npm install package@latest

# Run tests after updates (use Nx for affected analysis)
npx nx affected -t test
npx nx affected -t build
```

### Security Patching

**Security audit commands:**

```bash
# Run npm audit
npm audit

# Fix automatically where possible
npm audit fix

# Review and fix manually (requires jq: brew install jq on macOS, choco install jq on Windows)
npm audit --json | jq '.vulnerabilities'
```

---

## Angular Upgrade Planning

### Upgrade Assessment

**Before upgrading, assess:**

| Factor | Questions |
|--------|-----------|
| Breaking changes | What APIs changed? What's deprecated? |
| Third-party libs | Are dependencies compatible? |
| Testing scope | What needs regression testing? |
| Rollback plan | Can we roll back quickly? |
| Timeline | How long will migration take? |

### ATD Angular Version Support

ATD supports the current Angular major version plus one prior version. Check [angular.dev](https://angular.dev) for the latest release.

| Version Category | ATD Status | Action Required |
|------------------|------------|-----------------|
| Current major (n) | Active | Stay current with minor/patch |
| Previous major (n-1) | Supported | Upgrade within 6 months |
| Older (n-2) | Legacy | Plan upgrade immediately |
| Earlier versions | Unsupported | Urgent upgrade needed |

### Staged Upgrade Process

Upgrades progress through ATD's standard environments: Development → QA → XAT (performance and acceptance testing) → Production.

```text
1. Development Environment
   - Run ng update
   - Fix breaking changes
   - Run all tests

2. QA Environment
   - Deploy upgraded version
   - Full regression testing
   - Performance validation

3. XAT (Performance/Acceptance)
   - Deploy to production-like environment
   - Stakeholder sign-off
   - Performance baseline comparison

4. Production
   - Deploy during low-traffic window
   - Monitor closely for 24 hours
   - Keep rollback ready
```

### Upgrade Checklist

- [ ] Review Angular release notes
- [ ] Run `ng update` in development
- [ ] Update third-party dependencies
- [ ] Fix all compilation errors
- [ ] Fix all lint errors
- [ ] Run full test suite
- [ ] Manual smoke testing
- [ ] Performance benchmarking
- [ ] Deploy to QA
- [ ] QA sign-off
- [ ] Deploy to XAT
- [ ] Stakeholder sign-off
- [ ] Deploy to production
- [ ] Monitor for 24 hours

---

## Technical Debt Management

### Identifying Technical Debt

**Code quality indicators:**

| Indicator | Warning Signs |
|-----------|---------------|
| Complexity | Functions > 50 lines, deep nesting |
| Duplication | Copy-paste code, similar implementations |
| Coverage | Test coverage < 90% |
| Dependencies | Outdated packages, security vulnerabilities |
| Architecture | NgModules, manual subscriptions, no OnPush |

### Technical Debt Prioritization

**Priority matrix:**

| Impact | High Risk | Low Risk |
|--------|-----------|----------|
| **High** | Fix ASAP | Schedule for next sprint |
| **Low** | Schedule quarterly | Backlog (may not fix) |

**Business impact factors:**

- User-facing vs internal
- Critical path vs edge case
- Scaling bottleneck
- Security implication

### Debt Reduction Strategies

**Boy Scout Rule:**
"Leave the code better than you found it"

When touching a file:

- Fix obvious issues
- Update to modern patterns
- Add missing tests
- But scope the changes

**Dedicated debt sprints:**

- Allocate 10-20% of sprint capacity
- Focus on high-impact items
- Track debt reduction metrics

### Tracking Technical Debt

**Documentation:**

```markdown
# Technical Debt Register

## TD-001: Legacy Module Not Migrated to Standalone
- **Location:** src/app/features/legacy-orders/
- **Impact:** High (blocks zoneless migration)
- **Effort:** Medium (2-3 days)
- **Owner:** [Unassigned]
- **Target:** Q2 2026
```

---

## Deprecation Process

### When to Deprecate

| Criteria | Deprecate? |
|----------|------------|
| Feature unused (< 1% users) | Yes |
| Better alternative exists | Yes |
| Maintenance burden high | Yes |
| Still actively used | No (migrate first) |

### Deprecation Announcement

**Timeline:**

| Phase | Duration | Action |
|-------|----------|--------|
| Announcement | Day 0 | Notify users, update docs |
| Warning period | 90 days | Console warnings, migration docs |
| Soft removal | 30 days | Disabled by default, flag to enable |
| Hard removal | Day 120 | Code removed |

### Code Deprecation Patterns

**Mark deprecated code:**

```typescript
/**
 * @deprecated Use UserProfileComponent instead. Will be removed in v3.0.
 */
@Component({
  selector: 'atd-user-card-legacy',
  // ...
})
export class UserCardLegacyComponent {}

// In usage - console warning
if (!environment.production) {
  console.warn('UserCardLegacyComponent is deprecated. Use UserProfileComponent.');
}
```

**ESLint rule for deprecated usage:**

```json
// .eslintrc.json
{
  "rules": {
    "deprecation/deprecation": "warn"
  }
}
```

---

## End-of-Life Procedures

### EOL Assessment

**Criteria for retirement:**

- No active users
- Functionality replaced by another system
- Maintenance cost exceeds value
- Security cannot be maintained

### EOL Planning

**Timeline template:**

| Phase | Timeline | Action |
|-------|----------|--------|
| Announcement | T-90 days | Notify all stakeholders |
| Migration period | T-60 days | Assist users in migrating |
| Soft shutdown | T-30 days | Read-only mode |
| Hard shutdown | T-0 | Application offline |
| Cleanup | T+30 days | Infrastructure decommissioned |

### EOL Execution

**Shutdown checklist:**

- [ ] Redirect traffic to replacement/notice page
- [ ] Export/archive user data
- [ ] Document API consumers
- [ ] Notify dependent systems
- [ ] Remove from monitoring
- [ ] Archive codebase
- [ ] Decommission infrastructure
- [ ] Update documentation

### Post-EOL

**Archival requirements:**

| Item | Retention | Location |
|------|-----------|----------|
| Source code | Indefinite | Git archive |
| Data exports | Per policy | Secure storage |
| Documentation | 3 years | Confluence archive |
| Audit logs | Per policy | Log archive |

---

## Application Health Metrics

### Health Score Framework

**Composite health score (0-100):**

| Factor | Weight | Metrics |
|--------|--------|---------|
| Reliability | 30% | Uptime, error rate |
| Performance | 25% | LCP, TTI, API latency |
| Security | 25% | CVE count, audit findings |
| Maintainability | 20% | Test coverage, debt ratio |

### Monitoring Dashboard

**Key metrics to display:**

```text
┌─────────────────────────────────────────────────┐
│ Application Health Dashboard                     │
├─────────────────────────────────────────────────┤
│ Health Score: 85/100 (Good)                     │
├─────────────────────────────────────────────────┤
│ Reliability    │ ████████░░ 80%  │ 99.5% uptime │
│ Performance    │ █████████░ 90%  │ LCP 2.1s     │
│ Security       │ █████████░ 90%  │ 0 critical   │
│ Maintainability│ ████████░░ 80%  │ 91% coverage │
├─────────────────────────────────────────────────┤
│ Last Deploy: 2026-01-19 10:00                   │
│ Version: 1.5.2                                   │
│ Angular: 20.1.0                                  │
└─────────────────────────────────────────────────┘
```

### Health Reviews

**Quarterly health review agenda:**

1. Review health score trends
2. Identify declining metrics
3. Prioritize improvement actions
4. Plan maintenance work
5. Update technical debt register

---

## Capacity Planning

### Load Forecasting

**Factors to consider:**

| Factor | Data Source |
|--------|-------------|
| Historical traffic | Analytics, logs |
| Business growth | Sales forecasts |
| Seasonal patterns | Historical data |
| Marketing events | Campaign calendar |

### Scaling Strategies

**Frontend considerations:**

| Strategy | When to Use |
|----------|-------------|
| CDN caching | Static assets, reduce origin load |
| Edge caching | Personalized content at edge |
| Code splitting | Large bundles, slow initial load |
| Lazy loading | Feature routes not always used |

### Resource Optimization

**Bundle optimization checklist:**

- [ ] Tree shaking enabled
- [ ] Lazy loading for feature routes
- [ ] No unused dependencies
- [ ] Images optimized
- [ ] Source maps only in dev
- [ ] Production build flag enabled

---

## Related Documents

- [[14-Migration-Guides]] - Detailed migration procedures
- [[10-CI-CD-Integration]] - Deployment and release pipelines
- [[17-Production-Support]] - Incident response and support

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.3 | Defined XAT environment, fixed type assertion in directive, added backend service pattern for feature flags, clarified npm vs Nx usage, added jq install note, added cross-references, made version support table generic, added hotfix versioning guidance, replaced Renovate with Dependabot, removed CVE response process and maintenance windows sections |
| 2026-01-19 | 1.2 | Corrections: updated feature flag example to prefer @if pattern, fixed related documents |
| 2026-01-19 | 1.1 | Full content added: release management, feature flags, maintenance, EOL |
| 2026-01-12 | 1.0 | Initial stub created |
