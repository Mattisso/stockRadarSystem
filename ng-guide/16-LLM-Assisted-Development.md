---
title: "LLM-Assisted Development"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, llm-development, claude-code, mcp-servers]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# LLM-Assisted Development

**Back to:** [[00-Playbook-Index|Playbook Index]]

This section provides comprehensive guidance on using AI/LLM tools effectively for Angular development at ATD.

---

## Overview

### Why LLM-Assisted Development at ATD

LLM tools provide significant productivity benefits for Angular development:

| Benefit | Example |
|---------|---------|
| **Faster boilerplate** | Generate components, services, tests in seconds |
| **Learning acceleration** | Understand legacy code, learn new patterns |
| **Reduced context switching** | Get answers without leaving the IDE |
| **Better documentation** | Generate docs from code automatically |
| **Code review assistance** | Pre-review before human review |

### Approved Tools

| Tool | Status | Use Case |
|------|--------|----------|
| **Claude Code** | Primary | Agentic development, complex tasks |
| **Cursor** | Approved | AI-enhanced IDE, tab completion |
| **GitHub Copilot** | Approved | Inline code suggestions |
| **Claude (API/Web)** | Approved | Research, complex questions |
| **ChatGPT** | Approved | Research, documentation lookup |

### Security Considerations

**Critical: No proprietary code in public LLMs without approval.**

| Data Type | Public LLMs | Enterprise LLMs |
|-----------|-------------|-----------------|
| Open source code | ✅ Allowed | ✅ Allowed |
| ATD business logic | ❌ Prohibited | ✅ Allowed |
| Customer data | ❌ Never | ❌ Never |
| API keys/secrets | ❌ Never | ❌ Never |
| Internal architecture | ❌ Prohibited | ✅ Allowed |

**Safe practices:**

- Use anonymized code snippets when asking about patterns
- Remove company-specific naming before sharing
- Prefer local/enterprise LLM tools for sensitive code
- When in doubt, ask security team

---

## Claude Code (Primary Recommendation)

Claude Code is ATD's recommended LLM development tool for its powerful agentic capabilities.

### Installation and Setup

```bash
# Install Claude Code (macOS/Linux/WSL)
curl -fsSL https://claude.ai/install.sh | bash

# Alternative: Homebrew
brew install --cask claude-code

# Verify installation
claude --version

# First run - will prompt for authentication
claude
```

### Configuration for Angular Projects

#### .claude Directory Setup

Create a `.claude` folder in your project root:

```text
my-angular-app/
├── .claude/
│   ├── settings.json     # Project-specific settings
│   └── commands/         # Custom slash commands
│       ├── component.md
│       ├── service.md
│       └── test.md
├── CLAUDE.md             # Project instructions
└── ...
```

#### CLAUDE.md Project Instructions

Create a `CLAUDE.md` file in the project root with Angular-specific guidance:

```markdown
# Project: ATD Customer Portal

## Tech Stack
- Angular 20.x with standalone components
- NgRx for state management
- Jest for unit testing
- Nx monorepo structure

## Code Standards
- All components must use OnPush change detection
- All components must be standalone
- Use signal-based inputs for new components
- Use selectSignal for NgRx store access
- Component selectors must use 'atd-' prefix

## File Structure
- Features in `src/app/features/{feature-name}/`
- NgRx state in `+state/` folders
- Shared components in `libs/ui-*`

## Testing Requirements
- 90% coverage minimum
- Use MockStore for NgRx testing
- Use fixtures from `*.fixtures.ts` files

## Don't
- Don't use NgModules
- Don't use constructor injection (use inject())
- Don't use *ngIf/*ngFor (use @if/@for)
- Don't subscribe manually (use async pipe or selectSignal)
```

#### Custom Slash Commands

Custom commands can be created in `.claude/commands/` for project-specific workflows. However, for component and service generation, ATD recommends using the **Angular MCP** and **Nx MCP** servers instead of custom commands—they understand the monorepo structure and generate code following project conventions automatically.

See the [MCP Servers for Angular Development](#mcp-servers-for-angular-development) section for setup details.

### Effective Prompting for Angular

#### Component Generation

```text
Create a UserProfileCard component that:
- Displays user avatar, name, and email
- Has an "Edit" button that emits an event
- Uses signal input for the user data
- Follows ATD standards (standalone, OnPush, atd- prefix)
```

#### Service Creation

```text
Create a UserApiService that:
- Injects HttpClient using inject()
- Has methods: getAll(), getById(id), create(user), update(id, user), delete(id)
- Returns Observables (not subscribed)
- Maps API responses to domain User model
- Follows the *ApiService naming convention
```

#### Test Writing

```text
Write Jest tests for UserListPageComponent:
- Test that it displays loading spinner when loading is true
- Test that it renders user cards when users are loaded
- Test that clicking a user card emits the userSelected event
- Use MockStore with selectUsers and selectLoading selectors
```

#### Refactoring Requests

```text
Refactor this component to use modern Angular patterns:
- Convert *ngIf to @if
- Convert *ngFor to @for with track
- Replace @Input() with signal input
- Replace store.select() with store.selectSignal()
Keep the same functionality, just update the patterns.
```

### Claude Code Hooks

Configure hooks in `~/.claude/settings.json` or use `/hooks` command. Hooks trigger on specific events:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "npx nx affected -t lint --files=$CLAUDE_FILE_PATHS"
          }
        ]
      }
    ]
  }
}
```

Available hook events: `PreToolUse`, `PostToolUse`, `Notification`, `Stop`, `UserPromptSubmit`.

### Best Practices

#### Context Management

- Keep conversations focused on single tasks
- Use @file mentions to reference specific files
- Clear context when switching to new topics
- Reference CLAUDE.md for project standards

#### Iterative Development

```text
1. Start with a clear, specific request
2. Review generated code before accepting
3. Ask for modifications if needed
4. Test before committing
5. Refine prompts based on results
```

#### Code Review of Generated Code

**Always review generated code for:**

- [ ] Follows ATD standards (OnPush, standalone, signals)
- [ ] No security vulnerabilities
- [ ] Proper error handling
- [ ] Tests are meaningful (not just for coverage)
- [ ] No unnecessary complexity

---

## MCP Servers for Angular Development

MCP (Model Context Protocol) servers extend Claude Code with specialized capabilities. **ATD provides Angular and Nx MCP servers that are essential for effective Angular development.**

### What Are MCP Servers?

MCP servers provide Claude Code with:

- Access to external tools and APIs
- Specialized domain knowledge
- Integration with development workflows
- Real-time data access

### ATD's Angular/Nx MCP Servers

ATD maintains MCP servers specifically for Angular development in Nx monorepos:

| Server | Purpose | Key Capabilities |
|--------|---------|------------------|
| **Angular MCP** | Angular CLI integration | Generate components, services, pipes following ATD standards |
| **Nx MCP** | Nx workspace tooling | Run generators, understand project graph, affected commands |

These servers understand the monorepo structure and automatically apply ATD conventions (OnPush, standalone, signal inputs, `atd-` prefix) when generating code.

**Example prompts with MCP servers enabled:**

```text
"Generate a user-profile component in the customer-portal app"
→ Angular MCP creates component with correct path, standards, and imports

"Create a shared data-access library for user management"
→ Nx MCP scaffolds the library with proper project configuration

"Run tests for all projects affected by my changes"
→ Nx MCP executes nx affected -t test
```

### Configuring MCP Servers

For project-scoped servers (shared with team), create `.mcp.json` in project root:

```json
{
  "mcpServers": {
    "angular": {
      "command": "npx",
      "args": ["@anthropic-ai/angular-mcp-server"]
    },
    "nx": {
      "command": "npx",
      "args": ["@anthropic-ai/nx-mcp-server"]
    }
  }
}
```

Or add servers via CLI: `claude mcp add <name> --scope project`

User-scoped servers go in `~/.claude.json`.

### Other Useful MCP Servers

| Server | Purpose | Use Case |
|--------|---------|----------|
| **Filesystem** | File operations | Read/write project files |
| **Git** | Git operations | Commits, branches, diffs |
| **Browser** | Web automation | E2E testing, screenshots |
| **Fetch** | HTTP requests | API testing, documentation lookup |

### MCP Server Best Practices

**Performance:**

- Only enable servers you actively use
- Disable unused servers to reduce overhead

**Security:**

- Review server permissions before enabling
- Don't enable servers with excessive access
- Use project-scoped configurations

---

## Other LLM Tools

### GitHub Copilot

GitHub Copilot provides inline code suggestions in VS Code. While approved for use, ATD prefers Claude-based tools (Claude Code, Cursor) for more complex tasks.

**Setup:**

1. Install GitHub Copilot extension
2. Sign in with GitHub account
3. Enable in VS Code settings

**Angular-specific tips:**

```typescript
// Type a comment describing what you want
// Copilot will suggest implementation

// Create a signal input for user data
user = input.required<User>();  // Copilot suggests this

// Create a selector for filtered users
export const selectFilteredUsers = createSelector(
  // Copilot completes based on context
);
```

**Best for:**

- Quick inline completions
- Repetitive patterns
- Boilerplate code

### ChatGPT / Claude Web

Use web interfaces for:

| Use Case | Why Web Interface |
|----------|-------------------|
| Research questions | Longer conversations |
| Architecture decisions | Need to think through options |
| Learning new concepts | Interactive exploration |
| Documentation lookup | Quick reference |

**Not for:**

- Writing production code (use Claude Code instead)
- Sharing proprietary code

### Cursor AI

Cursor provides AI-enhanced IDE features. See [[15-IDE-Setup]] for setup details.

**Best for:**

- Multi-file generation (Composer)
- Codebase-aware suggestions
- Refactoring with AI assistance

---

## LLM Development Workflows

### Component Development Workflow

With Angular/Nx MCP servers enabled:

```text
1. Define requirements
   "I need a data table component for displaying orders in the sales app"

2. Generate component (MCP handles structure and conventions)
   → Angular MCP creates component with OnPush, signals, atd- prefix

3. Review and refine
   "Add sorting by column header click"

4. Generate tests
   "Write tests for the order-table component using MockStore"

5. Review tests and implementation
   Verify tests are meaningful

6. Commit changes
   "Create a commit for these changes"
```

### Test-Driven Development with LLMs

```text
1. Describe the feature behavior
   "When user clicks filter, only matching items show"

2. Ask for test first
   "Write a test for this behavior"

3. Review and approve test
   Ensure test captures requirement

4. Ask for implementation
   "Now implement the code to make this test pass"

5. Run tests
   npx nx test my-component

6. Iterate until passing
```

### Debugging with LLM Assistance

```text
1. Share the error message
   "I'm getting this error: [error]"

2. Provide context
   @component.ts @template.html
   "This happens when I click the submit button"

3. Ask for diagnosis
   "What could cause this?"

4. Get fix suggestions
   "How do I fix this?"

5. Verify fix
   Test the solution before committing
```

### Documentation Generation

```text
1. Point to the code
   @user.service.ts

2. Request documentation
   "Generate JSDoc comments for the public methods"

3. Review for accuracy
   Verify descriptions match actual behavior

4. Request README section
   "Write a README section explaining how to use this service"
```

---

## Common Pitfalls with LLM-Generated Code

### Outdated Angular Patterns

LLMs may suggest deprecated patterns:

| LLM Might Generate | Correct Pattern |
|--------------------|-----------------|
| `*ngIf="condition"` | `@if (condition) { }` |
| `*ngFor="let x of items"` | `@for (x of items; track x.id) { }` |
| `@Input() data: Data` | `data = input<Data>()` |
| `constructor(private svc: Svc)` | `svc = inject(Svc)` |
| NgModule declarations | Standalone components |

**Always verify generated code uses Angular 20+ patterns.**

### Over-Engineering

LLMs tend to add unnecessary complexity:

```typescript
// LLM might generate this (over-engineered)
export class UserService {
  private readonly cache = new Map<string, User>();
  private readonly retryConfig = { attempts: 3, delay: 1000 };
  private readonly logger = inject(LoggingService);
  // ... 200 lines of unnecessary abstraction
}

// What you actually need
export class UserApiService {
  private readonly http = inject(HttpClient);

  getUser(id: string): Observable<User> {
    return this.http.get<User>(`/api/users/${id}`);
  }
}
```

**Request simple solutions explicitly:**
"Keep it simple - just the basic implementation without extra features"

### Missing Error Handling

Generated code often lacks error handling:

```typescript
// LLM might generate (missing error handling)
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(loadUsers),
    switchMap(() => this.userService.getUsers()),
    map(users => loadUsersSuccess({ users }))
  )
);

// Should have error handling
loadUsers$ = createEffect(() =>
  this.actions$.pipe(
    ofType(loadUsers),
    switchMap(() =>
      this.userService.getUsers().pipe(
        map(users => loadUsersSuccess({ users })),
        catchError(error => of(loadUsersFailure({ error: error.message })))
      )
    )
  )
);
```

**Explicitly request error handling:**
"Include proper error handling with catchError"

### Security Issues to Watch For

Review generated code for:

| Issue | What to Look For |
|-------|------------------|
| XSS | `innerHTML`, `bypassSecurityTrust*` |
| Injection | String concatenation in queries |
| Auth bypass | Missing guards, unchecked permissions |
| Data exposure | Logging sensitive data |

### Testing Generated Code

**Never commit untested generated code.**

```bash
# Always run after generating code
npx nx affected -t lint
npx nx affected -t test
npx nx affected -t build
```

---

## ATD Guidelines for LLM Usage

### Approved Uses

| Use | Status |
|-----|--------|
| Generate boilerplate code | ✅ Approved |
| Write tests | ✅ Approved |
| Refactor code | ✅ Approved |
| Generate documentation | ✅ Approved |
| Explain legacy code | ✅ Approved |
| Debug issues | ✅ Approved |
| Code review assistance | ✅ Approved |

### Prohibited Uses

| Use | Status | Reason |
|-----|--------|--------|
| Share customer data | ❌ Prohibited | Privacy/compliance |
| Share API keys/secrets | ❌ Prohibited | Security |
| Commit without review | ❌ Prohibited | Quality |
| Skip testing | ❌ Prohibited | Quality |

### Code Attribution

ATD does not require attribution for AI-generated code, but:

- You are responsible for all code you commit
- AI-generated code must meet same standards as human code
- Review requirements apply equally to AI-generated code

### Review Requirements for Generated Code

All generated code must:

1. **Pass linting:** `npx nx affected -t lint`
2. **Pass tests:** `npx nx affected -t test`
3. **Be human reviewed:** Same as any other code
4. **Follow ATD standards:** OnPush, standalone, signals
5. **Include tests:** Generated code needs generated tests

---

## Quick Reference

### Claude Code Commands

```bash
# Start Claude Code in project directory
claude

# Resume a previous session
claude --resume

# Continue last conversation
claude --continue
```

**Inside Claude Code (slash commands):**

| Command | Purpose |
|---------|---------|
| `/help` | Show available commands |
| `/compact` | Compact conversation to save context |
| `/clear` | Clear conversation history |
| `/model` | Change AI model |
| `/cost` | Show token usage |
| `/init` | Initialize CLAUDE.md for project |

### Effective Prompt Patterns

```text
# Be specific about ATD standards
"Create a component following ATD standards (OnPush, standalone, atd- prefix)"

# Request simple solutions
"Keep it simple - basic implementation only"

# Include error handling
"Include proper error handling"

# Request tests
"Also generate Jest tests using MockStore"
```

### Verification Checklist

- [ ] Code uses Angular 20+ patterns
- [ ] OnPush change detection
- [ ] Standalone component
- [ ] Signal-based inputs (new components)
- [ ] No security vulnerabilities
- [ ] Error handling included
- [ ] Tests included and meaningful
- [ ] Lint passes
- [ ] Build passes

---

## Related Documents

- [[02-Modern-Angular-Patterns]] - Target patterns for generated code
- [[11-Code-Review-Standards]] - Reviewing generated code
- [[13-Common-Pitfalls]] - Avoiding LLM-generated mistakes
- [[15-IDE-Setup]] - IDE configuration with AI tools
- [[ATD-Online-AI-Integration-index]] - ATD AI integration project

**External Resources:**

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code) - Official setup and usage guide
- [MCP Servers](https://github.com/modelcontextprotocol/servers) - Available MCP server implementations

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Updated Claude Code installation, hooks, MCP config; emphasized Angular/Nx MCP servers |
| 2026-01-19 | 1.1 | Full content added: Claude Code, MCP servers, workflows, guidelines |
| 2026-01-08 | 1.0 | Initial stub created |
