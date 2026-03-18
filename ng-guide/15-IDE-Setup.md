---
title: "IDE Setup"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, ide-setup, vscode, cursor, intellij]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# IDE Setup

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## Overview

This guide covers IDE setup for Angular development at ATD. Three IDEs are supported:

| IDE | Recommendation | Best For |
|-----|----------------|----------|
| **VS Code** | Primary | Most developers, best Angular ecosystem |
| **Cursor** | Recommended for AI | AI-assisted development workflows |
| **IntelliJ/WebStorm** | Supported | Developers from Java backgrounds |

---

## VS Code (Primary Recommendation)

VS Code is the primary recommendation due to excellent Angular ecosystem support and team familiarity.

### Required Extensions

These extensions are required for Angular development at ATD:

#### Angular Language Service

```text
Extension ID: Angular.ng-template
```

Provides:

- IntelliSense in templates
- Go to definition for components, directives
- Error checking in templates
- Autocomplete for bindings

#### ESLint

```text
Extension ID: dbaeumer.vscode-eslint
```

Provides:

- Real-time lint error display
- Auto-fix on save
- Integration with project ESLint config

#### Prettier

```text
Extension ID: esbenp.prettier-vscode
```

Provides:

- Consistent code formatting
- Format on save
- Integration with project Prettier config

#### Nx Console

```text
Extension ID: nrwl.angular-console
```

Provides:

- Visual UI for Nx commands
- Project visualization
- Generator wizards
- Task running interface

### Recommended Extensions

These extensions improve productivity but are not required:

| Extension | ID | Purpose |
|-----------|-------|---------|
| GitLens | `eamodio.gitlens` | Git blame, history |
| Error Lens | `usernamehw.errorlens` | Inline error display |
| Todo Tree | `gruntfuggly.todo-tree` | Track TODOs in codebase |
| Path Intellisense | `christian-kohler.path-intellisense` | Path autocomplete |
| Material Icon Theme | `pkief.material-icon-theme` | File icons |

### Browser Extensions

Install **Angular DevTools** for Chrome or Edge:

- Component tree inspection
- Change detection profiling
- Dependency injection explorer
- Router state visualization

Install from the Chrome Web Store or Edge Add-ons (see External Resources).

### Workspace Settings

Create `.vscode/settings.json` in the project root:

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit",
    "source.organizeImports": "explicit"
  },

  "typescript.format.insertSpaceAfterOpeningAndBeforeClosingNonemptyBraces": true,

  "files.exclude": {
    "**/*.js": {
      "when": "$(basename).ts"
    }
  },
  "typescriptHero.imports.insertSpaceBeforeAndAfterImportBraces": true,
  "typescriptHero.imports.multiLineTrailingComma": false,
  "typescriptHero.imports.multiLineWrapThreshold": 140,
  "typescriptHero.imports.organizeOnSave": true,
  "[typescript]": {
    "editor.rulers": [140],
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  },
  "[html]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[scss]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[json]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[yaml]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
}
```

### Recommended Extensions File

Create `.vscode/extensions.json` to recommend extensions to team:

```json
{
  "recommendations": [
    "angular.ng-template",
    "dbaeumer.vscode-eslint",
    "EditorConfig.EditorConfig",
    "esbenp.prettier-vscode",
    "vitest.explorer",
    "infinity1207.angular2-switcher",
    "nrwl.angular-console",
    "rbbit.typescript-hero",
    "streetsidesoftware.code-spell-checker",
  ]
}
```

### Debugging Configuration

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Launch Chrome",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:4200",
      "webRoot": "${workspaceFolder}"
    },
    {
      "name": "Attach to Chrome",
      "type": "chrome",
      "request": "attach",
      "port": 9222,
      "webRoot": "${workspaceFolder}"
    },
    {
      "name": "Debug Jest Tests",
      "type": "node",
      "request": "launch",
      "runtimeArgs": [
        "--inspect-brk",
        "${workspaceRoot}/node_modules/jest/bin/jest.js",
        "--runInBand",
        "--config",
        "${workspaceRoot}/jest.config.ts"
      ],
      "console": "integratedTerminal"
    }
  ]
}
```

**To debug in Chrome:**

1. Start the dev server: `npx nx serve my-app`
2. Press F5 or select "Launch Chrome" from Debug panel
3. Set breakpoints in TypeScript files
4. Breakpoints will hit when code executes

### Tasks Configuration

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Serve",
      "type": "shell",
      "command": "npx nx serve",
      "group": "build",
      "problemMatcher": []
    },
    {
      "label": "Test",
      "type": "shell",
      "command": "npx nx test",
      "group": "test",
      "problemMatcher": []
    },
    {
      "label": "Lint",
      "type": "shell",
      "command": "npx nx lint",
      "group": "build",
      "problemMatcher": ["$eslint-stylish"]
    },
    {
      "label": "Build",
      "type": "shell",
      "command": "npx nx build",
      "group": "build",
      "problemMatcher": []
    }
  ]
}
```

### Keyboard Shortcuts

Useful shortcuts for Angular development:

| Action | Windows/Linux | Mac |
|--------|---------------|-----|
| Go to Definition | F12 | F12 |
| Find All References | Shift+F12 | Shift+F12 |
| Rename Symbol | F2 | F2 |
| Quick Fix | Ctrl+. | Cmd+. |
| Format Document | Shift+Alt+F | Shift+Option+F |
| Toggle Terminal | Ctrl+` | Cmd+` |
| Go to File | Ctrl+P | Cmd+P |
| Command Palette | Ctrl+Shift+P | Cmd+Shift+P |
| Toggle Sidebar | Ctrl+B | Cmd+B |

---

## Cursor (AI-Enhanced Development)

Cursor is a VS Code fork with built-in AI capabilities, useful for AI-assisted Angular development.

### Why Cursor for Angular Development

| Feature | Benefit |
|---------|---------|
| **Tab completion** | AI-powered code suggestions |
| **Chat context** | Reference files with @mentions |
| **Composer** | Multi-file generation for components |
| **Codebase awareness** | AI understands your project structure |

### Setup from VS Code Migration

Cursor can import VS Code settings automatically:

1. Install Cursor (see External Resources)
2. On first launch, select "Import from VS Code"
3. Settings, extensions, and keybindings transfer automatically

### Extension Compatibility

Most VS Code extensions work in Cursor:

| Extension | Compatibility |
|-----------|---------------|
| Angular Language Service | ✅ Full support |
| ESLint | ✅ Full support |
| Prettier | ✅ Full support |
| Nx Console | ✅ Full support |
| GitLens | ✅ Full support |

### AI Features for Angular

**Tab Completion:**

```typescript
// Type partial code, press Tab to accept suggestion
@Component({
  selector: 'atd-user-card',
  // AI suggests: changeDetection: OnPush, imports: [...]
})
```

**Chat Context with @mentions:**

```text
@user-card.component.ts How can I add input validation?
@+state/users.reducer.ts Add a new action for filtering
```

**Composer for Components:**

Use Cmd/Ctrl+I to open Composer for multi-file generation:

```text
Prompt: "Create a user profile page component with NgRx state"

Generates:
- user-profile-page.component.ts
- user-profile-page.component.html
- user-profile-page.component.scss
- +state/user-profile.actions.ts
- +state/user-profile.reducer.ts
- +state/user-profile.selectors.ts
```

### Cursor-Specific Settings

Cursor inherits VS Code settings. Additional Cursor-specific configuration:

1. **Codebase Indexing:** Enable via Cursor Settings → Features → Codebase Indexing
2. **Model Selection:** Configure preferred AI model in Cursor Settings → Models
3. **Tab Completion:** Adjust aggressiveness in Cursor Settings → Features → Copilot++

Cursor's settings UI changes frequently; refer to Cursor documentation for current options.

### When to Use Cursor vs VS Code

| Use Cursor When | Use VS Code When |
|-----------------|------------------|
| Writing new components | Debugging complex issues |
| Generating boilerplate | Team standardization required |
| Learning Angular patterns | Maximum stability needed |
| Refactoring with AI assistance | Offline development |

### Note on AI Assistants

While GitHub Copilot is a popular AI coding assistant available for VS Code, ATD prefers using Claude-based tools for AI-assisted development. Cursor's built-in AI uses multiple models including Claude. See [[16-LLM-Assisted-Development]] for detailed guidance on AI-assisted workflows.

---

## IntelliJ IDEA / WebStorm

IntelliJ IDEA (Ultimate) and WebStorm provide excellent Angular support, preferred by developers from Java backgrounds.

### Angular Plugin Setup

Angular support is built into WebStorm and IntelliJ Ultimate:

1. File → Settings → Plugins
2. Search "Angular"
3. Ensure the Angular plugin is enabled
4. Restart IDE

### Project Configuration

**Import Project:**

1. File → Open
2. Select the project root folder
3. IntelliJ auto-detects Nx/Angular structure

**Configure Node:**

1. File → Settings → Languages & Frameworks → Node.js
2. Set Node interpreter path
3. Enable "Coding assistance for Node.js"

**Configure TypeScript:**

1. File → Settings → Languages & Frameworks → TypeScript
2. Enable TypeScript language service
3. Point to project's `tsconfig.json`

### Run Configurations

**Create Serve Configuration:**

1. Run → Edit Configurations
2. Click + → npm
3. Name: "Serve"
4. Scripts: "start" (or configure command: `npx nx serve`)
5. Apply

**Create Test Configuration:**

1. Run → Edit Configurations
2. Click + → Jest
3. Name: "Test All"
4. Configuration file: Select `jest.config.ts`
5. Apply

### Debugging Setup

**Debug Angular Application:**

1. Create JavaScript Debug configuration
2. URL: `http://localhost:4200`
3. Start the dev server
4. Run debug configuration
5. Set breakpoints in TypeScript files

**Debug Jest Tests:**

1. Right-click on test file
2. Select "Debug 'test-name'"
3. Breakpoints work automatically

### Code Style Settings

1. File → Settings → Editor → Code Style → TypeScript
2. Set indent to 2 spaces
3. Enable "Use single quotes"
4. Import settings from `.editorconfig`

### Refactoring Tools

IntelliJ provides powerful refactoring:

| Refactoring | Shortcut (Windows) | Shortcut (Mac) |
|-------------|-------------------|----------------|
| Rename | Shift+F6 | Shift+F6 |
| Extract Method | Ctrl+Alt+M | Cmd+Option+M |
| Extract Variable | Ctrl+Alt+V | Cmd+Option+V |
| Move File | F6 | F6 |
| Safe Delete | Alt+Delete | Cmd+Delete |

### Key Differences from VS Code

| Feature | VS Code | IntelliJ/WebStorm |
|---------|---------|-------------------|
| Startup time | Fast | Slower |
| Memory usage | Lower | Higher |
| Refactoring | Good | Excellent |
| Git integration | Good (with GitLens) | Excellent built-in |
| Angular templates | Good | Excellent |
| Price | Free | Paid (free for students) |
| Nx integration | Nx Console extension | Built-in support |

---

## Common Configuration

These configurations should be consistent across all IDEs.

### EditorConfig Standards

Create `.editorconfig` in project root:

```ini
# EditorConfig helps maintain consistent coding styles
# https://editorconfig.org

root = true

[*]
charset = utf-8
indent_style = space
indent_size = 2
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false

[*.{json,yml,yaml}]
indent_size = 2

[Makefile]
indent_style = tab
```

### Prettier Configuration

Create `.prettierrc` in project root:

```json
{
  "singleQuote": true,
  "trailingComma": "es5",
  "printWidth": 100,
  "tabWidth": 2,
  "semi": true,
  "bracketSpacing": true,
  "arrowParens": "avoid"
}
```

Create `.prettierignore`:

```text
dist
coverage
node_modules
.angular
*.min.js
```

### ESLint Configuration

The ESLint configuration is managed by Nx. Key settings in `.eslintrc.json`:

```json
{
  "root": true,
  "ignorePatterns": ["**/*"],
  "plugins": ["@nx"],
  "overrides": [
    {
      "files": ["*.ts"],
      "extends": [
        "plugin:@nx/typescript",
        "plugin:@angular-eslint/recommended"
      ],
      "rules": {
        "@angular-eslint/component-selector": [
          "error",
          {
            "type": "element",
            "prefix": "atd",
            "style": "kebab-case"
          }
        ]
      }
    },
    {
      "files": ["*.html"],
      "extends": ["plugin:@angular-eslint/template/recommended"]
    }
  ]
}
```

### Git Hooks with Husky

Set up pre-commit hooks:

```bash
# Install Husky
npm install husky --save-dev
npx husky init

# Create pre-commit hook
echo "npx lint-staged" > .husky/pre-commit
```

Configure lint-staged in `package.json`:

```json
{
  "lint-staged": {
    "*.{ts,html}": ["eslint --fix"],
    "*.{ts,html,scss,json,md}": ["prettier --write"]
  }
}
```

### Shared Team Settings

Commit these files to the repository:

| File | Purpose |
|------|---------|
| `.vscode/settings.json` | VS Code workspace settings |
| `.vscode/extensions.json` | Recommended extensions |
| `.vscode/launch.json` | Debug configurations |
| `.editorconfig` | Editor-agnostic settings |
| `.prettierrc` | Prettier configuration |
| `.eslintrc.json` | ESLint configuration |
| `.husky/pre-commit` | Pre-commit hooks |

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Angular Language Service not working | Restart VS Code, check extension is enabled |
| ESLint not showing errors | Check `.eslintrc.json` exists, restart ESLint server |
| Prettier not formatting | Check file is not in `.prettierignore`, verify default formatter |
| Debugging not hitting breakpoints | Ensure source maps enabled in `angular.json` |
| Nx Console not detecting project | Check `nx.json` exists in root |

### Reset VS Code Angular Extension

If Angular Language Service misbehaves:

1. Cmd/Ctrl+Shift+P
2. "Angular: Restart Angular Language Server"

### Clear Nx Cache

If Nx behaves unexpectedly:

```bash
npx nx reset
```

---

## Related Documents

- [[01-Getting-Started]] - Initial environment setup
- [[03-Nx-Workspace-Setup]] - Nx workspace configuration
- [[12-ATD-Conventions]] - Code style settings
- [[16-LLM-Assisted-Development]] - AI development tools

**External Resources:**

- [Cursor](https://cursor.sh) - AI-enhanced VS Code fork
- [Angular DevTools](https://angular.dev/tools/devtools) - Browser extension for debugging

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Updated for Angular 20/esbuild; added Angular DevTools; AI assistant notes |
| 2026-01-19 | 1.1 | Full content added: VS Code, Cursor, IntelliJ, common config |
| 2026-01-08 | 1.0 | Initial stub created |
