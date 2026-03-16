---
title: "Accessibility Standards"
created: 2026-01-08 10:00
updated: 2026-01-21 10:00
tags: [playbook, angular, work, atd-standards, accessibility, cdk, a11y]
context: Angular Development Playbook for ATD
status: active
angular_version: "20.x"
playbook_version: "1.2"
audience: [new-developers, experienced-developers]
---

# Accessibility Standards

**Back to:** [[00-Playbook-Index|Playbook Index]]

---

## ATD Accessibility Approach

### Current State

ATD does not mandate a specific WCAG compliance level. However, accessibility is valued and encouraged, particularly for customer-facing applications.

| Application Type | Accessibility Attention |
|------------------|------------------------|
| Customer-facing | Higher priority, more thorough implementation |
| Internal tools | More relaxed, but still encouraged |

### Guiding Principle

While not strictly enforced, ATD leans toward doing the right thing for accessibility. Several key team members advocate for proper a11y implementation, and developers are encouraged to follow best practices.

---

## Design System Integration

ATD has design system standards for accessibility including:

- Color contrast ratios
- Focus indicators
- Component theming

**For specific design standards, reference:**

- ATD Design Team Figma files
- Component system themes
- Design team documentation

These design specifications are maintained separately from this playbook.

---

## Angular CDK Accessibility

ATD primarily uses the Angular CDK (Component Dev Kit) rather than full Angular Material. The CDK provides essential accessibility utilities.

### CDK A11y Module

Import accessibility utilities from `@angular/cdk/a11y`:

```typescript
import { A11yModule } from '@angular/cdk/a11y';
import { FocusMonitor, LiveAnnouncer, FocusTrap } from '@angular/cdk/a11y';
```

### Focus Management

Use `FocusMonitor` to track focus origin and apply appropriate styles:

```typescript
@Component({
  imports: [A11yModule]
})
export class MyComponent {
  private readonly focusMonitor = inject(FocusMonitor);
  private readonly elementRef = inject(ElementRef);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    this.focusMonitor.monitor(this.elementRef, true);

    this.destroyRef.onDestroy(() => {
      this.focusMonitor.stopMonitoring(this.elementRef);
    });
  }
}
```

### Focus Trapping

For modals and dialogs, trap focus within the container:

```typescript
@Component({
  template: `
    <div cdkTrapFocus [cdkTrapFocusAutoCapture]="true">
      <h2>Modal Title</h2>
      <div>Modal content...</div>
      <button (click)="close()">Close</button>
    </div>
  `
})
export class ModalComponent {}
```

### Live Announcements

Announce dynamic content changes to screen readers:

```typescript
@Component({ /* ... */ })
export class NotificationComponent {
  private readonly liveAnnouncer = inject(LiveAnnouncer);

  showSuccess(message: string): void {
    this.liveAnnouncer.announce(message, 'polite');
  }

  showError(message: string): void {
    this.liveAnnouncer.announce(message, 'assertive');
  }
}
```

---

## Best Practices

### Semantic HTML First

Use semantic HTML elements before reaching for ARIA:

```html
<!-- GOOD: Semantic HTML -->
<button (click)="submit()">Submit</button>
<nav>...</nav>
<main>...</main>
<article>...</article>

<!-- AVOID: ARIA on non-semantic elements -->
<div role="button" (click)="submit()">Submit</div>
```

### Accessible Forms

Properly associate labels with form controls:

```html
<!-- GOOD: Explicit label association -->
<label for="email">Email Address</label>
<input id="email" type="email" formControlName="email" />

<!-- GOOD: Implicit association -->
<label>
  Email Address
  <input type="email" formControlName="email" />
</label>

<!-- With error messages -->
<input
  id="email"
  type="email"
  formControlName="email"
  [attr.aria-describedby]="emailErrors() ? 'email-error' : null"
  [attr.aria-invalid]="emailErrors()"
/>
@if (emailErrors()) {
  <span id="email-error" class="error">{{ emailErrors() }}</span>
}
```

### Interactive Elements

Ensure all interactive elements are accessible:

```typescript
// Buttons should be <button>, not <div>
@Component({
  template: `
    <!-- GOOD -->
    <button (click)="handleClick()">Click me</button>

    <!-- If must use non-button, add role and keyboard handling -->
    <div
      role="button"
      tabindex="0"
      (click)="handleClick()"
      (keydown.enter)="handleClick()"
      (keydown.space)="handleClick()">
      Click me
    </div>
  `
})
```

### Images and Icons

Provide appropriate text alternatives:

```html
<!-- Informative image -->
<img src="chart.png" alt="Sales increased 25% in Q4" />

<!-- Decorative image -->
<img src="decorative-border.png" alt="" />

<!-- Icon buttons need labels -->
<button aria-label="Close dialog">
  <svg aria-hidden="true"><!-- icon SVG --></svg>
</button>

<!-- Icon with visible text doesn't need aria-label -->
<button>
  <svg aria-hidden="true"><!-- icon SVG --></svg>
  Save
</button>
```

---

## Keyboard Navigation

### Tab Order

Maintain logical tab order:

```html
<!-- Use natural DOM order, avoid positive tabindex -->
<header>...</header>
<nav tabindex="0">...</nav>  <!-- Only if not naturally focusable -->
<main>
  <button>First action</button>
  <button>Second action</button>
</main>

<!-- AVOID: Positive tabindex disrupts natural flow -->
<button tabindex="3">Third</button>
<button tabindex="1">First</button>
<button tabindex="2">Second</button>
```

### Focus on Route Changes

Consider managing focus when navigating:

```typescript
@Component({
  template: `<main #mainContent tabindex="-1">...</main>`
})
export class AppComponent {
  private readonly router = inject(Router);

  readonly mainContent = viewChild<ElementRef>('mainContent');

  constructor() {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd),
      takeUntilDestroyed()
    ).subscribe(() => {
      this.mainContent()?.nativeElement.focus();
    });
  }
}
```

### Skip Links

For content-heavy pages, provide skip navigation:

```html
<a href="#main-content" class="skip-link">Skip to main content</a>
<header>...</header>
<nav>...</nav>
<main id="main-content" tabindex="-1">
  ...
</main>
```

```scss
.skip-link {
  position: absolute;
  left: -9999px;

  &:focus {
    left: 0;
    top: 0;
    z-index: 1000;
  }
}
```

---

## Visual Accessibility

### Color Contrast

Follow WCAG guidelines for contrast:

| Element | Minimum Ratio |
|---------|---------------|
| Normal text | 4.5:1 |
| Large text (18px+ bold, 24px+) | 3:1 |
| UI components, graphics | 3:1 |

Reference ATD design system for approved color combinations.

### Focus Indicators

Never remove focus indicators without providing alternatives:

```scss
// WRONG: Removes all focus indication
button:focus {
  outline: none;
}

// CORRECT: Custom focus style
button:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.5);
}

// CORRECT: Use focus-visible for keyboard-only focus
button:focus-visible {
  outline: 2px solid var(--focus-color);
  outline-offset: 2px;
}
```

### Text Sizing

Use relative units to support browser zoom:

```scss
// GOOD: Relative units
.heading {
  font-size: 1.5rem;
}

.body {
  font-size: 1rem;
  line-height: 1.5;
}

// AVOID: Fixed pixel sizes for text
.heading {
  font-size: 24px;
}
```

### Reduced Motion

Respect user preferences for reduced motion:

```scss
// Disable animations when user prefers reduced motion
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

// Or apply selectively
.animated-element {
  transition: transform 300ms ease;

  @media (prefers-reduced-motion: reduce) {
    transition: none;
  }
}
```

In TypeScript, detect the preference:

```typescript
@Component({ /* ... */ })
export class AnimatedComponent {
  readonly prefersReducedMotion = signal(
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  constructor() {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    mediaQuery.addEventListener('change', (e) => {
      this.prefersReducedMotion.set(e.matches);
    });
  }
}
```

---

## ARIA Guidelines

### When to Use ARIA

1. **First**: Use semantic HTML
2. **Second**: Use CDK/Material components with built-in a11y
3. **Last resort**: Add ARIA attributes

### Common ARIA Patterns

**Expandable content:**

```html
<button
  [attr.aria-expanded]="isExpanded()"
  aria-controls="content-panel">
  Toggle Details
</button>
<div id="content-panel" [hidden]="!isExpanded()">
  Expandable content...
</div>
```

**Loading states:**

```html
<div
  [attr.aria-busy]="loading()"
  aria-live="polite">
  @if (loading()) {
    <span>Loading...</span>
  } @else {
    <span>Content loaded</span>
  }
</div>
```

**Required fields with reactive forms:**

```typescript
@Component({
  template: `
    <label for="name">
      Name
      @if (nameRequired()) {
        <span class="required-indicator">(required)</span>
      }
    </label>
    <input
      id="name"
      type="text"
      formControlName="name"
      [attr.aria-required]="nameRequired()"
      [attr.aria-invalid]="nameInvalid()"
      [attr.aria-describedby]="nameInvalid() ? 'name-error' : null"
    />
    @if (nameInvalid()) {
      <span id="name-error" role="alert">Name is required</span>
    }
  `
})
export class FormComponent {
  readonly form = inject(FormBuilder).group({
    name: ['', Validators.required]
  });

  readonly nameRequired = computed(() =>
    this.form.controls.name.hasValidator(Validators.required)
  );

  readonly nameInvalid = computed(() =>
    this.form.controls.name.invalid && this.form.controls.name.touched
  );
}
```

---

## Deferred Loading Accessibility

When using `@defer` blocks, ensure lazy-loaded content remains accessible:

```html
<!-- Provide loading and error states for screen readers -->
@defer (on viewport) {
  <section aria-label="Product reviews">
    <app-reviews [productId]="productId()" />
  </section>
} @placeholder {
  <div aria-hidden="true">Reviews loading area</div>
} @loading (minimum 500ms) {
  <div role="status" aria-live="polite">
    <span class="sr-only">Loading reviews...</span>
    <app-spinner />
  </div>
} @error {
  <div role="alert">
    Failed to load reviews. <button (click)="retry()">Retry</button>
  </div>
}
```

Key considerations for `@defer`:

| Concern | Solution |
|---------|----------|
| Loading state | Use `role="status"` with `aria-live="polite"` |
| Error state | Use `role="alert"` for immediate announcement |
| Placeholder | Can use `aria-hidden="true"` if purely decorative |
| Focus management | Ensure focus moves appropriately when content loads |

---

## Testing Accessibility

### Manual Testing Checklist

Before releasing, especially for customer-facing apps:

- [ ] All functionality accessible via keyboard
- [ ] Tab order is logical
- [ ] Focus is visible at all times
- [ ] Images have appropriate alt text
- [ ] Forms have associated labels
- [ ] Color is not the only means of conveying information
- [ ] Text can be resized to 200% without loss of functionality

### Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| Lighthouse | Automated a11y audit | Chrome DevTools |
| axe DevTools | Browser extension | Manual spot checks |
| Keyboard | Navigation testing | Tab through entire page |
| Screen reader | Verification | VoiceOver (Mac), NVDA (Windows) |

### Lighthouse Accessibility Audit

Run Lighthouse periodically, especially before releases:

```bash
npx lighthouse https://your-app-url --only-categories=accessibility --view
```

### Automated Testing with jest-axe

Integrate accessibility testing into your unit test suite:

```typescript
import { axe, toHaveNoViolations } from 'jest-axe';
import { render } from '@testing-library/angular';

expect.extend(toHaveNoViolations);

describe('MyComponent accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = await render(MyComponent);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have no violations with specific rules', async () => {
    const { container } = await render(MyComponent);
    const results = await axe(container, {
      rules: {
        'color-contrast': { enabled: true },
        'label': { enabled: true }
      }
    });
    expect(results).toHaveNoViolations();
  });
});
```

For Cypress E2E tests, use `cypress-axe`:

```typescript
describe('Page accessibility', () => {
  it('should be accessible', () => {
    cy.visit('/');
    cy.injectAxe();
    cy.checkA11y();
  });
});
```

---

## LLM and Browser Automation Considerations

Modern LLMs increasingly interact with web applications through browser automation tools. These tools rely heavily on accessibility features to understand and navigate interfaces.

### Why This Matters

- **AI assistants** use semantic HTML and ARIA attributes to understand page structure
- **Automated testing tools** leverage accessibility APIs to interact with elements
- **Screen readers and LLMs** both benefit from the same accessibility patterns

### Best Practices for LLM-Compatible Interfaces

| Practice | Benefit |
|----------|---------|
| Semantic HTML elements | LLMs can understand element purpose |
| Descriptive `aria-label` | Provides context for ambiguous elements |
| Unique, meaningful IDs | Enables precise element targeting |
| Clear button/link text | Actions are understandable without visual context |
| Proper form labels | Input purposes are clear |
| Logical heading hierarchy | Document structure is parseable |

### Example: LLM-Friendly Component

```html
<!-- Clear, semantic, automatable -->
<form aria-label="User registration">
  <fieldset>
    <legend>Account Information</legend>

    <label for="email-input">Email address</label>
    <input
      id="email-input"
      type="email"
      formControlName="email"
      aria-describedby="email-hint"
    />
    <span id="email-hint">We'll send a confirmation to this address</span>

    <button type="submit" aria-describedby="submit-status">
      Create Account
    </button>
    <span id="submit-status" aria-live="polite">{{ statusMessage() }}</span>
  </fieldset>
</form>
```

Building accessible applications benefits both human users with assistive technologies and the growing ecosystem of AI-powered tools interacting with web interfaces.

---

## Component Checklist

When building components, consider:

| Item | Check |
|------|-------|
| Semantic HTML | Using appropriate elements? |
| Keyboard access | All interactions keyboard accessible? |
| Focus management | Focus handled appropriately? |
| Labels | All inputs/buttons labeled? |
| Color | Not relying solely on color? |
| Motion | Respecting `prefers-reduced-motion`? |

---

## CDK Accessibility Patterns

The CDK provides low-level accessibility primitives that ATD uses to build accessible components without the full Material library.

### CDK Overlay for Dialogs

Use `@angular/cdk/overlay` for dialogs with proper focus management:

```typescript
import { Overlay, OverlayRef } from '@angular/cdk/overlay';
import { ComponentPortal } from '@angular/cdk/portal';

@Component({ /* ... */ })
export class DialogService {
  private readonly overlay = inject(Overlay);

  open<T>(component: ComponentType<T>): OverlayRef {
    const overlayRef = this.overlay.create({
      hasBackdrop: true,
      positionStrategy: this.overlay.position()
        .global()
        .centerHorizontally()
        .centerVertically()
    });

    const portal = new ComponentPortal(component);
    overlayRef.attach(portal);

    return overlayRef;
  }
}
```

Combine with `cdkTrapFocus` in the dialog component for complete focus management.

### CDK ListKeyManager

For keyboard navigation in lists and menus:

```typescript
import { ListKeyManager } from '@angular/cdk/a11y';

@Component({
  template: `
    <ul role="listbox" (keydown)="onKeydown($event)">
      @for (item of items(); track item.id) {
        <li
          role="option"
          [class.active]="keyManager?.activeItem === item"
          [attr.aria-selected]="keyManager?.activeItem === item">
          {{ item.label }}
        </li>
      }
    </ul>
  `
})
export class ListComponent implements AfterViewInit {
  @ContentChildren(ListItemDirective) listItems!: QueryList<ListItemDirective>;

  keyManager: ListKeyManager<ListItemDirective> | null = null;

  ngAfterViewInit(): void {
    this.keyManager = new ListKeyManager(this.listItems)
      .withWrap()
      .withHomeAndEnd()
      .withTypeAhead();
  }

  onKeydown(event: KeyboardEvent): void {
    this.keyManager?.onKeydown(event);
  }
}
```

### When to Use CDK Patterns

Rely on CDK for complex accessibility patterns:

- **Overlay/Portal** - Dialogs, tooltips, dropdowns
- **ListKeyManager** - Keyboard navigation in lists/menus
- **FocusTrap** - Modal focus containment
- **LiveAnnouncer** - Screen reader notifications
- **FocusMonitor** - Focus origin tracking

---

## Related Documents

- [[04-Component-Architecture]] - Component patterns
- [[07-Testing-Strategies]] - Testing approaches
- [[11-Code-Review-Standards]] - Review checklist

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 1.2 | Modernized to pure CDK patterns; added DestroyRef/takeUntilDestroyed; added prefers-reduced-motion, @defer accessibility, jest-axe testing, and LLM browser automation sections |
| 2026-01-14 | 1.1 | Full content added from interview |
| 2026-01-08 | 1.0 | Initial stub created |
