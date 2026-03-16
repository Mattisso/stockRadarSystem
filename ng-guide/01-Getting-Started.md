---
title: "Getting Started with Angular at ATD"
created: 2026-01-08 10:00
updated: 2026-01-12 10:00
tags: [playbook, angular, work, atd-standards, getting-started]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers]
---

# Getting Started with Angular at ATD

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

> [!note] This is not a beginner's guide
> This playbook assumes you already have Angular experience. It focuses on ATD-specific practices, conventions, and best practices rather than teaching Angular fundamentals.

## Prerequisites

### Required Knowledge

Before working on Angular projects at ATD, you should be comfortable with:

- **Angular fundamentals** - Components, services, modules, routing, dependency injection
- **RxJS basics** - Observables, operators, subscriptions
- **TypeScript** - Types, interfaces, generics, decorators
- **Git** - Branching, merging, pull requests
- **Command line** - Basic terminal navigation and commands

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| RAM | 16GB | 32GB |
| Disk Space | 50GB free | 100GB free |
| OS | macOS, Windows, or Linux | macOS or Linux |

---

## Development Environment Setup

### Node.js and npm

ATD standardizes on **Node 22.x LTS**. Use [nvm](https://github.com/nvm-sh/nvm) (Node Version Manager) to manage Node versions:

```bash
# Install nvm (macOS/Linux)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Install Node 22 LTS
nvm install 22
nvm use 22

# Verify installation
node --version  # Should show v22.x.x
npm --version
```

Most ATD repos include an `.nvmrc` file. Run `nvm use` in the project root to automatically switch to the correct version.

### Angular CLI

Install the Angular CLI globally:

```bash
npm install -g @angular/cli@20
```

### Nx CLI

Nx commands are typically run via `npx` to ensure you're using the workspace's version:

```bash
# No global install required - use npx
npx nx --version
```

If you prefer a global install:

```bash
npm install -g nx@latest
```

---

## IDE Setup

> [!tip] Detailed IDE Setup
> For comprehensive IDE configuration including debugging, keyboard shortcuts, and advanced settings, see [[15-IDE-Setup]].

### Quick VS Code Setup

Install these essential extensions to get started:

| Extension | ID | Purpose |
|-----------|-----|---------|
| Angular Language Service | `angular.ng-template` | IntelliSense, errors, navigation |
| Nx Console | `nrwl.angular-console` | GUI for Nx commands |
| Prettier | `esbenp.prettier-vscode` | Code formatting |
| Angular Switcher | `infinity1207.angular2-switcher` | Quick switch between component files (.ts, .html, .scss) |
| ESLint | `dbaeumer.vscode-eslint` | Linting |

Install all at once via command line:

```bash
code --install-extension angular.ng-template
code --install-extension nrwl.angular-console
code --install-extension esbenp.prettier-vscode
code --install-extension infinity1207.angular2-switcher
code --install-extension dbaeumer.vscode-eslint
```

---

## Joining an Existing Project

Most new developers at ATD will join an existing project rather than creating one from scratch.

### Cloning and Setup

```bash
# Clone the repository
git clone <repo-url>
cd <project-name>

# Use correct Node version (if .nvmrc exists)
nvm use

# Install dependencies
npm install
```

### Project Structure Overview

ATD Angular projects use Nx and typically follow this structure:

```
project-root/
├── apps/                    # Application projects
│   └── my-app/
│       ├── src/
│       │   ├── app/         # Application code
│       │   ├── assets/      # Static assets
│       │   └── environments/# Environment configs
│       └── project.json     # App-specific Nx config
├── libs/                    # Shared libraries
│   └── shared/
│       └── ui/              # Reusable UI components
├── nx.json                  # Nx workspace config
├── package.json
├── tsconfig.base.json
└── .nvmrc                   # Node version specification
```

**Key files to understand:**

- `nx.json` - Workspace-wide Nx configuration
- `project.json` - Per-project build/serve/test targets
- `tsconfig.base.json` - Shared TypeScript configuration

> [!note] Monorepos at ATD
> Currently, most ATD projects use one repo per application. However, we're exploring monorepos for related applications (e.g., ATD Online). The Nx structure above supports both patterns.

---

## Running and Building

All commands use `npx nx` to ensure you're running the workspace's Nx version.

### Development Server

```bash
# Start dev server (typically at http://localhost:4200)
npx nx serve <app-name>

# With specific port
npx nx serve <app-name> --port=4201
```

### Building

```bash
# Development build
npx nx build <app-name>

# Production build
npx nx build <app-name> --configuration=production
```

### Running Tests

```bash
# Unit tests
npx nx test <app-name>

# Unit tests in watch mode
npx nx test <app-name> --watch

# Linting
npx nx lint <app-name>

# E2E tests (if configured)
npx nx e2e <app-name>-e2e
```

---

## Connecting to ATD Backend Services

### Development Approach

Most local development at ATD connects to our **development environment** backends rather than running services locally. This ensures you're working with realistic data and service behavior.

For cases requiring local backend services, coordinate with your team lead for setup instructions.

### Proxy Configuration

Create or modify `proxy.conf.json` in your app's root to route API calls:

```json
{
  "/api/*": {
    "target": "https://dev-api.atd.com",
    "secure": true,
    "changeOrigin": true,
    "logLevel": "debug"
  }
}
```

Configure the proxy in `project.json`:

```json
{
  "serve": {
    "options": {
      "proxyConfig": "apps/my-app/proxy.conf.json"
    }
  }
}
```

Then run:

```bash
npx nx serve <app-name>
```

API calls to `/api/*` will be proxied to the target backend.

---

## Troubleshooting Common Setup Issues

### Zscaler Configuration

ATD uses Zscaler for network security. Common issues:

**SSL certificate errors with npm/git:**

```bash
# If you see UNABLE_TO_VERIFY_LEAF_SIGNATURE errors
# Your IT team can provide the Zscaler root certificate

# Configure npm to use the certificate
npm config set cafile /path/to/zscaler-cert.pem

# Or for git
git config --global http.sslCAInfo /path/to/zscaler-cert.pem
```

Contact IT if you're having persistent certificate issues.

### NPM Registry Access

Verify you can reach the npm registry:

```bash
npm ping
```

If using a private registry, ensure your `.npmrc` is configured correctly. Check with your team for the correct registry URL.

### Node Version Conflicts

If you see unexpected errors, verify your Node version matches the project's `.nvmrc`:

```bash
nvm use
node --version
```

### Permission Issues

Avoid using `sudo` with npm. If you hit permission errors:

```bash
# Fix npm permissions (macOS/Linux)
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'

# Add to your shell profile (.bashrc, .zshrc, etc.)
export PATH=~/.npm-global/bin:$PATH
```

---

## Next Steps

After completing setup:

1. [[02-Modern-Angular-Patterns]] - Learn modern Angular patterns (signals, control flow)
2. [[03-Nx-Workspace-Setup]] - Deep dive into Nx tooling
3. [[04-Component-Architecture]] - Start building components

---

## Related Documents

- [[15-IDE-Setup]] - Comprehensive IDE configuration
- [[12-ATD-Conventions]] - ATD coding standards
- [[03-Nx-Workspace-Setup]] - Nx workspace details

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-12 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
