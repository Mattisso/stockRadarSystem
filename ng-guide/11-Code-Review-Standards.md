---
title: "Code Review Standards"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, code-review]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# Code Review Standards

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## PR Checklist

### Pre-Submit Checklist

Before creating a PR, verify:

**Code Quality**

- [ ] All lint rules pass (`npx nx affected -t lint`)
- [ ] All tests pass (`npx nx affected -t test`)
- [ ] Coverage meets 90%+ threshold
- [ ] No console.log statements left in code
- [ ] No commented-out code (unless with explanation)

**Angular Standards**

- [ ] Components use `ChangeDetectionStrategy.OnPush`
- [ ] Components are standalone
- [ ] Using signal-based inputs for new components
- [ ] No business logic in components (use selectors/services)
- [ ] No manual subscriptions (use async pipe, `store.selectSignal()`, or `toSignal()`)

**Security**

- [ ] No hardcoded credentials or API keys
- [ ] User input is validated/sanitized
- [ ] No SQL injection or XSS vulnerabilities
- [ ] Sensitive data not logged

**Documentation**

- [ ] Complex logic has explanatory comments
- [ ] PR description explains the "why"
- [ ] Breaking changes documented

### Reviewer Checklist

When reviewing PRs, check:

| Area | Key Questions |
|------|--------------|
| **Purpose** | Does the code solve the stated problem? |
| **Design** | Does the approach make sense? Is it over-engineered? |
| **Tests** | Are critical paths tested? Edge cases covered? |
| **Security** | Any potential vulnerabilities? |
| **Performance** | Any obvious performance issues? |
| **Maintainability** | Will someone understand this in 6 months? |

---

## Review Focus Areas

### Security Review Points

Security issues are **critical** - block merge until resolved.

**Automated Security Checks:**

A security-focused GitHub Action runs on all PRs, scanning for:
- Known vulnerabilities in dependencies
- Recommendations for library updates
- Common security anti-patterns

For security-sensitive changes, involve the ATD Security Team for manual review.

| Issue | What to Look For |
|-------|------------------|
| **SQL Injection** | String concatenation in queries, unparameterized inputs |
| **XSS** | Unsanitized user input in templates, `bypassSecurityTrust*` usage |
| **Auth Bypass** | Missing route guards, unchecked permissions |
| **Data Exposure** | Sensitive data in logs, exposed in responses |
| **Secrets** | Hardcoded API keys, passwords, tokens |

**Code patterns to flag:**

```typescript
// SECURITY RISK: SQL injection
const query = `SELECT * FROM users WHERE id = ${userId}`;

// SECURITY RISK: XSS vulnerability
this.innerHTML = userInput;
this.sanitizer.bypassSecurityTrustHtml(userInput);

// SECURITY RISK: Exposed credentials
const apiKey = 'sk-12345...';
```

### Performance Review Points

| Issue | What to Look For |
|-------|------------------|
| **Change Detection** | Missing `OnPush`, function calls in templates |
| **Memory Leaks** | Unsubscribed observables, event listeners not cleaned |
| **N+1 Queries** | API calls inside loops, missing pagination |
| **Bundle Size** | Large library imports, missing lazy loading |
| **Inefficient Code** | Unnecessary iterations, redundant calculations |

**Code patterns to flag:**

```typescript
// PERFORMANCE: Missing OnPush (default behavior when omitted)
@Component({
  // No changeDetection specified = Default (should add OnPush)
})

// PERFORMANCE: Function call in template (runs every CD cycle)
<div>{{ formatDate(item.date) }}</div>

// PERFORMANCE: API call in loop
items.forEach(item => {
  this.http.get(`/api/details/${item.id}`).subscribe(...);  // N+1!
});
```

### Accessibility Review Points

For customer-facing applications especially:

| Item | Requirement |
|------|-------------|
| **Semantic HTML** | Using `<button>` not `<div role="button">` |
| **Form labels** | All inputs have associated labels |
| **Keyboard access** | All interactions keyboard accessible |
| **Focus management** | Focus visible, logical tab order |
| **Alt text** | Images have appropriate alternatives |

Reference [[09-Accessibility-Standards]] for detailed patterns.

### Code Quality Points

| Area | Standard |
|------|----------|
| **Component size** | Components under 300 lines; split if larger |
| **Function length** | Functions under 50 lines; extract if longer |
| **Nesting depth** | Max 3-4 levels of nesting |
| **Naming** | Clear, descriptive names following conventions |
| **DRY** | No copy-paste duplication |
| **Single responsibility** | One clear purpose per file/function |

**Angular-specific quality:**

```typescript
// QUALITY: NgRx in presentational component (wrong)
export class UserCardComponent {
  private store = inject(Store);  // Dumb components shouldn't access store
}

// QUALITY: Logic in component (move to selector)
export class UserListPageComponent {
  get filteredUsers() {  // Move to NgRx selector
    return this.users.filter(u => u.active);
  }
}

// QUALITY: Manual subscription (use selectSignal or toSignal instead)
ngOnInit() {
  this.store.select(selectUsers).subscribe(users => {
    this.users = users;
  });
}

// PREFERRED: Signal-based approach
readonly users = this.store.selectSignal(selectUsers);
// or: readonly users = toSignal(this.store.select(selectUsers));
```

---

## Common Review Feedback

### Frequently Caught Issues

| Issue | Frequency | Fix |
|-------|-----------|-----|
| Missing `OnPush` | Very common | Add to all components |
| Function calls in templates | Common | Use pipes or computed signals |
| Missing test coverage | Common | Add tests for public methods |
| NgRx in dumb components | Occasional | Move store access to parent |
| Unsubscribed observables | Occasional | Use `takeUntilDestroyed()` |
| Hardcoded values | Occasional | Move to environment config |

### Constructive Feedback Examples

**Be specific and actionable:**

```text
// GOOD feedback
"This filter logic should be in a selector rather than the component.
See selectFilteredUsers in user.selectors.ts for the pattern."

// WEAK feedback
"This doesn't follow our patterns."
```

**Explain the why:**

```text
// GOOD feedback
"Using OnPush here would improve performance since this component
re-renders frequently. With OnPush, it only updates when inputs change."

// WEAK feedback
"Add OnPush."
```

### How to Address Feedback

When receiving feedback:

1. **Understand first** - Ask clarifying questions if needed
2. **Respond to each comment** - Acknowledge or explain your reasoning
3. **Don't take it personally** - Feedback is about code, not you
4. **Learn patterns** - If you see the same feedback repeatedly, internalize the pattern

When disagreeing:

```text
"I see the concern, but I chose this approach because [reason].
Happy to change if you still think it's better the other way."
```

---

## Review Process

### Draft PRs

Use draft PRs for:

- Early feedback on approach before full implementation
- Work in progress that's not ready for review
- Sharing code for discussion

Convert to "Ready for Review" when:

- All CI checks pass
- Self-review complete
- Description explains changes

### Required Reviewers

| Change Type | Required Reviewers |
|-------------|-------------------|
| Feature code | 1 team member |
| NgRx changes | 1 senior developer |
| Shared library changes | 2 reviewers |
| Security-sensitive changes | 1 senior + security review |
| Infrastructure/CI changes | DevOps team member |
| Dependabot PRs | 1 team member (run full test suite locally) |

> **Planned:** CODEOWNERS files will be added to repositories (especially the monorepo) to automate reviewer assignment based on file paths.

### Dependabot PR Reviews

Dependabot PRs require slightly different handling:

1. Review the changelog for breaking changes
2. Run the full unit test suite locally (not just affected)
3. For major version bumps, coordinate with team before merging
4. Security updates should be prioritized

### Approval Requirements

| Requirement | Standard |
|-------------|----------|
| Minimum approvals | 1 (2 for shared libraries) |
| CI checks | All must pass |
| Conversations | All must be resolved |
| Stale reviews | Re-request after significant changes |

### Review Turnaround

**Expected (not required):** First review within 4 hours during business hours.

- Smaller PRs (<200 lines) get faster reviews
- Large PRs may be asked to split
- Ping reviewer in Slack if urgent
- This is a team expectation, not an enforced policy

---

## AI-Assisted Reviews

ATD uses Claude (via GitHub integration) to augment (not replace) human code reviews.

### What AI Reviews Check

Claude provides initial analysis for:

| Area | AI Capability |
|------|---------------|
| Security vulnerabilities | SQL injection, XSS, credential exposure |
| Performance patterns | N+1 queries, change detection issues |
| Code quality | Complexity, duplication, best practices |
| Missing error handling | Unhandled exceptions, missing null checks |

### Human Review Responsibility

AI reviews are **advisory**. Humans must verify:

| Area | Why Human Review |
|------|------------------|
| **Business logic** | AI doesn't understand requirements |
| **Architecture decisions** | Context-dependent choices |
| **Team conventions** | Patterns specific to ATD |
| **UX implications** | User experience considerations |
| **False positives** | AI may flag intentional patterns |

### Working with Claude Feedback

- Claude's comments are marked with 🤖 indicator in the PR
- Dismiss false positives with explanation
- Report persistent false positives to improve prompts
- Never skip human review because Claude "approved"

---

## Commit Message Standards

### Format

ATD uses **Conventional Commits** format:

```text
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Types

| Type | Use For |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code change that neither fixes nor adds feature |
| `test` | Adding or updating tests |
| `chore` | Maintenance, dependencies, tooling |
| `perf` | Performance improvement |

### Rules

| Rule | Example |
|------|---------|
| Subject ≤50 characters | `feat(user): add profile avatar upload` |
| Imperative mood | "add" not "added" or "adds" |
| No period at end | `fix(cart): resolve quantity update bug` |
| Body wraps at 72 characters | Use body for "why", not "what" |

### Examples

**Simple change:**

```text
fix(auth): handle expired token redirect
```

**Change with body:**

```text
feat(orders): add bulk order export functionality

Allows users to export up to 1000 orders at once to CSV format.
Export is processed asynchronously to avoid blocking the UI.

Closes #1234
```

**Breaking change:**

```text
feat(api)!: change user endpoint response format

BREAKING CHANGE: User response now includes nested address object.
Previous flat structure is deprecated.

Migration: Update all consumers to use user.address.city instead of user.city
```

### AI-Assisted Commit Messages

AI tools can help generate well-formatted commit messages. Stage your changes, then use your preferred AI assistant to analyze the diff and suggest a conventional commit message. Review and adjust the suggestion before committing.

---

## PR Description Template

> **Planned:** This template will be added to repositories as `.github/PULL_REQUEST_TEMPLATE.md` to auto-populate new PRs.

```markdown
## Summary
<!-- What does this PR do? Why? -->

## Changes
<!-- List key changes -->
- Added X component
- Updated Y service to handle Z
- Fixed bug in W

## Testing
<!-- How was this tested? -->
- [ ] Unit tests added/updated
- [ ] Manual testing completed
- [ ] E2E tests (if applicable)

## Screenshots
<!-- If UI changes, add before/after screenshots -->

## Related
<!-- Link to tickets, related PRs -->
Closes #123
Related to #456
```

---

## Review Best Practices

### For Authors

| Practice | Reason |
|----------|--------|
| Keep PRs small (<300 lines) | Easier to review thoroughly |
| Self-review before requesting | Catch obvious issues |
| Write clear descriptions | Help reviewers understand context |
| Respond promptly to feedback | Keep reviews moving |
| Split unrelated changes | Each PR should have one purpose |

### For Reviewers

| Practice | Reason |
|----------|--------|
| Review promptly | Don't block teammates |
| Be constructive | Suggest solutions, not just problems |
| Praise good code | Reinforce positive patterns |
| Ask questions | If unclear, ask rather than assume |
| Use "nit" prefix for minor issues | Distinguish critical from optional |

### Review Comments

Use prefixes to indicate severity:

| Prefix | Meaning |
|--------|---------|
| (none) | Must fix before merge |
| `nit:` | Nice to have, optional |
| `question:` | Clarification needed |
| `suggestion:` | Alternative approach to consider |

---

## Related Documents

- [[07-Testing-Strategies]] - Test coverage requirements
- [[09-Accessibility-Standards]] - A11y review points
- [[10-CI-CD-Integration]] - CI checks that must pass
- [[12-ATD-Conventions]] - Coding style references
- [[16-LLM-Assisted-Development]] - AI tools for development

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Clarified signal patterns, Claude/GitHub AI reviews, security team/action, Dependabot review process; added CODEOWNERS and PR template notes |
| 2026-01-19 | 1.1 | Full content added: checklists, focus areas, commit standards |
| 2026-01-08 | 1.0 | Initial stub created |
