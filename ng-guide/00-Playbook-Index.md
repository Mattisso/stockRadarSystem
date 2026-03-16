---
title: "ATD Angular Development Playbook"
created: 2026-01-08 10:00
updated: 2026-01-12 10:00
tags: [playbook, angular, work, atd-standards, index]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers, tech-leads]
---

# ATD Angular Development Playbook

**Document Version:** 1.0
**Last Updated:** 2026-01-08
**Angular Version:** 20.x
**Purpose:** Master overview and navigation for ATD Angular development standards

---

## Table of Contents

- [Who Is This For?](#who-is-this-for)
- [Quick Start Guide](#quick-start-guide)
- [Documentation Index](#documentation-index)
- [Version History](#version-history)
- [Contributing](#contributing)

---

## Who Is This For?

This playbook serves two primary audiences with different starting points.

### New-to-Angular Developers

**Start here if:** You know programming (TypeScript, JavaScript) but Angular is new to you.

**Your learning path:**

1. [[01-Getting-Started]] - Set up your development environment
2. [[02-Modern-Angular-Patterns]] - Learn modern Angular patterns (signals, control flow)
3. [[03-Nx-Workspace-Setup]] - Understand ATD's Nx-based project structure
4. [[04-Component-Architecture]] - Master standalone components
5. [[07-Testing-Strategies]] - Write tests for your code

**Timeline suggestion:** Work through sections 01-04 in your first week, then branch into specific topics as needed.

### Experienced Angular Developers New to ATD

**Start here if:** You know Angular but are new to ATD's specific patterns and conventions.

**Your learning path:**

1. [[03-Nx-Workspace-Setup]] - ATD's Nx workspace patterns (even for standalone apps)
2. [[12-ATD-Conventions]] - Company-specific standards and naming conventions
3. [[05-State-Management]] - When to use Signals vs NgRx at ATD
4. [[10-CI-CD-Integration]] - ATD's GitHub Actions and GoCD pipeline
5. [[11-Code-Review-Standards]] - PR checklist and review expectations

**Timeline suggestion:** Review sections 03 and 12 immediately, then explore other sections as you encounter those areas in your work.

---

## Quick Start Guide

### Your First Day

1. **Environment Setup**
   - Follow [[01-Getting-Started]] to install required tools
   - Set up your IDE using [[15-IDE-Setup]]
   - Clone the relevant repository (see [[ATD-Repository-Links]])

2. **Understand the Codebase**
   - Review [[03-Nx-Workspace-Setup]] for project structure
   - Read [[12-ATD-Conventions]] for naming and style guidelines

3. **Get Help**
   - Set up Claude Code with [[16-LLM-Assisted-Development]]
   - Review [[External-Resources]] for Angular documentation links

### Your First Week

1. **Build Something**
   - Create a feature using [[04-Component-Architecture]] patterns
   - Implement state management following [[05-State-Management]]
   - Connect to APIs using [[06-API-Integration]]

2. **Quality Assurance**
   - Write tests following [[07-Testing-Strategies]]
   - Check accessibility with [[09-Accessibility-Standards]]
   - Submit PR following [[11-Code-Review-Standards]]

3. **Deep Dive**
   - Explore [[02-Modern-Angular-Patterns]] for modern syntax
   - Review [[13-Common-Pitfalls]] to avoid common mistakes

---

## Documentation Index

### Fundamentals

| Document | Focus | Audience |
|----------|-------|----------|
| [[01-Getting-Started]] | Development environment setup | All |
| [[02-Modern-Angular-Patterns]] | Signals, control flow, inject() | All |
| [[03-Nx-Workspace-Setup]] | Nx monorepo/standalone tooling | All |

### Architecture & Patterns

| Document | Focus | Audience |
|----------|-------|----------|
| [[04-Component-Architecture]] | Standalone component patterns | All |
| [[05-State-Management]] | Signals vs NgRx decision guide | Intermediate |
| [[06-API-Integration]] | HTTP services, interceptors | All |
| [[19-Service-Workers]] | Caching, PWA, micro-frontend support | Intermediate |

### Quality & Operations

| Document | Focus | Audience |
|----------|-------|----------|
| [[07-Testing-Strategies]] | Unit, integration, E2E testing | All |
| [[08-Performance-Optimization]] | Change detection, lazy loading | Intermediate |
| [[09-Accessibility-Standards]] | WCAG, ARIA, keyboard navigation | All |
| [[10-CI-CD-Integration]] | GitHub Actions, GoCD pipelines | DevOps |
| [[11-Code-Review-Standards]] | PR checklist, review guide | All |
| [[17-Production-Support]] | Incident response, monitoring, hotfixes | DevOps, Tech Leads |
| [[18-Application-Lifecycle]] | Releases, maintenance, EOL procedures | Tech Leads |

### ATD-Specific

| Document | Focus | Audience |
|----------|-------|----------|
| [[12-ATD-Conventions]] | Company naming and style standards | All |
| [[13-Common-Pitfalls]] | Anti-patterns and how to fix them | All |
| [[14-Migration-Guides]] | Angular version upgrade guides | Tech Leads |

### Developer Tools

| Document | Focus | Audience |
|----------|-------|----------|
| [[15-IDE-Setup]] | VS Code, Cursor, IntelliJ configuration | All |
| [[16-LLM-Assisted-Development]] | Claude Code, MCP servers, AI workflows | All |

### Reference

| Document | Focus |
|----------|-------|
| [[Angular-Version-Changelog]] | Angular version tracking and breaking changes |
| [[ATD-Repository-Links]] | Links to ATD Angular repositories |
| [[External-Resources]] | Official Angular docs and tutorials |

---

## Version History

This playbook version is tied to the Angular version it documents.

| Angular Version | Playbook Version | Status | Key Changes |
|-----------------|------------------|--------|-------------|
| 20.x | 1.1 | Current | Updated for Angular 20 |
| 19.x | 1.0 | Previous | Initial playbook release |
| 21.x | 2.0 | Future | (Planned) |

### Version-Specific Content

Throughout the playbook, version-specific content is marked with callouts:

> [!info] Angular 19+
> This pattern requires Angular 19 or later.

> [!warning] Deprecated
> This approach is deprecated. See migration guide.

---

## Contributing

### How to Update This Playbook

1. **Minor Updates** (typos, clarifications)
   - Edit the relevant document directly
   - Update the `updated` field in frontmatter

2. **New Content**
   - Add content to the appropriate section document
   - Update this index if adding new documents
   - Add relevant tags to frontmatter

3. **Angular Version Updates**
   - When a new Angular version releases:
     - Update [[Angular-Version-Changelog]] with breaking changes
     - Review all documents for outdated patterns
     - Add deprecation callouts where needed
     - Update [[14-Migration-Guides]] with upgrade steps
     - Increment playbook version

### Content Guidelines

- **Keep it practical**: Include code examples, not just theory
- **Link liberally**: Cross-reference related documents
- **Mark versions**: Note which Angular version a pattern requires
- **Update the changelog**: Document changes at the bottom of each file

---

## Related Links

- [[Enterprise-Architecture-Audit]] - ATD's architecture standards
- [[ATD-Online-Monorepo-CICD-Pipeline]] - Monorepo CI/CD patterns

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-12 | 1.1 | Updated for Angular 20, renamed Modern Patterns doc to be version-agnostic |
| 2026-01-12 | 1.0 | Added Production Support and Application Lifecycle documents |
| 2026-01-08 | 1.0 | Initial playbook framework created |
