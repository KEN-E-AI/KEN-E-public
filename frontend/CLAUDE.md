# CLAUDE.md - Frontend

This file provides detailed guidance for working with the KEN-E frontend codebase. For general project guidelines and best practices, refer to the [root CLAUDE.md](../CLAUDE.md).

## Frontend Overview

The KEN-E frontend is a modern React TypeScript application built with Vite, featuring a comprehensive component library based on Radix UI and styled with TailwindCSS. It provides a dashboard interface for marketing analytics and insights.

## Core Framework & Technologies

- **React 18** with TypeScript
- **Vite**: Fast builds and HMR with React SWC plugin
- **React Router 6**: Client-side routing for SPA
- **TailwindCSS 3**: Utility-first styling with custom configuration
- **Radix UI**: Accessible component primitives (~50 UI components)
- **TanStack Query**: Server state management
- **Firebase Auth**: Authentication system
- **Axios**: HTTP client for API communication
- **React Hook Form + Zod**: Form handling and validation

## Common Development Commands

- `npm run dev` - Start development server on port 8080 (uses default development mode)
- `npm run dev:development` - Start development server with development environment
- `npm run dev:staging` - Start development server with staging environment
- `npm run dev:production` - Start development server with production environment (use with caution!)
- `npm run build` - Build for production
- `npm run build:staging` - Build for staging environment
- `npm run build:production` - Build for production environment
- `npm run test` - Run Vitest tests
- `npm run typecheck` - Run TypeScript type checking
- `npm run format.fix` - Format code with Prettier
- `npm run preview` - Preview production build locally

## Project Structure

```
frontend/src/
├── components/
│   ├── ui/               # ~50 reusable UI components
│   ├── auth/            # Authentication components
│   ├── dashboard/       # Dashboard-specific components
│   ├── home/           # Home page components
│   ├── configuration/  # Settings and config components
│   └── layout/         # Layout components
├── contexts/           # React contexts (AuthContext)
├── data/              # Static and mock data
├── hooks/             # Custom React hooks
├── lib/               # Utilities and configurations
├── pages/             # Page components
└── types/             # TypeScript type definitions
```

## Routing System

Routing is managed by React Router v6 with protected routes:

- **Public routes**: `/login`, `/signup`
- **Protected routes**: All dashboard pages require authentication
- **Dynamic routes**: Use React Router params (e.g., `/analysis-report/:reportId`)
- Routes are defined in `src/App.tsx`
- Page components are in `src/pages/`

Key routes:

- `/` - Home page
- `/performance` - Performance dashboard
- `/big-bets` - Big bets page
- `/exploration` - Exploration page
- `/insights` - Insights page
- `/knowledge/*` - Knowledge base section
- `/account-settings`, `/user-settings` - Settings pages

## Styling System

### CSS File Structure

**IMPORTANT**: Be aware of the CSS cascade and file hierarchy:

1. **`src/App.css`**: This file should be kept minimal or empty. Default Vite/React templates include global styles here that can interfere with the dashboard layout:

   ```css
   /* AVOID these common template styles that break dashboard layouts: */
   #root {
     text-align: center; /* Centers ALL text globally */
     max-width: 1280px; /* Constrains app width */
     margin: 0 auto; /* Centers the entire app */
     padding: 2rem; /* Adds unwanted padding */
   }
   ```

2. **`src/index.css`**: Contains Tailwind directives and CSS custom properties (variables). This is where global styles should go:

   - CSS variables for colors (using oklch color space)
   - Base styles using `@layer base`
   - Component-specific overrides

3. **Component styles**: Use Tailwind utility classes directly in components. Avoid inline styles or separate CSS files.

### TailwindCSS Configuration

The `tailwind.config.ts` file defines the design system:

- Custom color palette with semantic naming
- Extended theme with dashboard-specific colors
- Dark mode support via CSS variables
- Custom animations and transitions

### The `cn()` Utility

The codebase uses a custom `cn()` utility function that combines `clsx` and `tailwind-merge`:

```typescript
import { cn } from "@/lib/utils"

// Basic usage
<div className={cn("base-class", conditionalClass && "conditional-class")} />

// Complex example
function CustomComponent({ size, isFullWidth, hasError, className, ...props }) {
  return (
    <div
      className={cn(
        // Base styles always applied
        "flex items-center rounded-md transition-all duration-200",

        // Object syntax for conditional classes
        {
          "text-xs p-1.5 gap-1": size === "sm",
          "text-sm p-2 gap-2": size === "md",
          "text-base p-3 gap-3": size === "lg",
          "w-full": isFullWidth,
        },

        // Conditional with && operator
        hasError && "border-red-500 text-red-700 bg-red-50",

        // User-provided className comes last for override capability
        className
      )}
      {...props}
    />
  );
}
```

### Dark Mode

Dark mode is implemented using:

- CSS variables defined in `src/index.css`
- TailwindCSS dark mode classes
- Theme toggle component (if implemented)

### Accessibility: `text-tertiary` allowlist

`--color-text-tertiary` fails WCAG AA contrast and is formally exempt — usage is limited to decorative/secondary text (timestamps, helper copy, dim icons, disabled states). Any new file under `src/components` or `src/pages` that uses `text-tertiary` (or `text-[var(--color-text-tertiary)]`) must, in the same PR, either be added to `ALLOWED_FILES` in `src/test/text-tertiary-audit.test.ts` with a short rationale tag, or carry `// allow-text-tertiary: <reason>` on each offending line. The audit runs in CI as part of the `frontend-a11y-tests` step; on failure the test prints the exact line to paste. See `docs/design/components/ui/accessibility-baseline.md` §Exemptions for background.

## UI Component Library

The project includes ~50 pre-built UI components in `src/components/ui/`:

**Layout:** `Card`, `Separator`, `ScrollArea`
**Form:** `Button`, `Input`, `Textarea`, `Select`, `Checkbox`, `RadioGroup`, `Switch`, `Form` (React Hook Form integration)
**Feedback:** `Alert`, `Toast`, `Progress`, `Skeleton`
**Overlay:** `Dialog`, `Sheet`, `Popover`, `Tooltip`, `DropdownMenu`, `ContextMenu`
**Data Display:** `Table`, `DataTable` (with TanStack Table), `Badge`, `Avatar`
**Navigation:** `Tabs`, `NavigationMenu`, `Breadcrumb`

## Authentication State

```tsx
import { useAuth } from "@/contexts/AuthContext";

function MyComponent() {
  const { user, selectedOrganization, selectedAccount, signOut } = useAuth();

  if (!user) {
    return <Navigate to="/login" />;
  }
}
```

## API Integration

API calls use Axios with Firebase Auth token injection. See `src/lib/api.ts` for the configured instance and interceptors.

## Gating a feature behind a flag

> **Prerequisite:** This recipe requires FF-PRD-03 (Frontend SDK + E2E) to have shipped. The files referenced below (`FeatureFlagsContext`, `registry.ts`, and the runtime `useFeatureFlag` hook) are delivered by that PRD and do not exist until it merges.

When shipping a feature behind a flag, follow the four steps below. The full contract lives in the [Feature Flags component README](../docs/design/components/feature-flags/README.md).

```ts
// 1. Add the key to frontend/src/lib/featureFlags/registry.ts
export const KNOWN_FLAGS = [
  "automations_beta" as FlagKey,
];

// 2. Use the hook where the feature is rendered
const { enabled } = useFeatureFlag("automations_beta" as FlagKey);
if (!enabled) return <LegacyView />;
return <NewView />;

// 3. Ask a super-admin to create the flag in /admin/feature-flags
//    with targeting rules + owner + expected_ga_release.

// 4. In dev, toggle with ?ff.automations_beta=on
```

**Dev override:** in non-production environments, toggle a flag for the current browser tab with `?ff.<key>=on` or `?ff.<key>=off`. See [README §7.7](../docs/design/components/feature-flags/README.md#77-dev-override-non-production-only) for persistence and production-gating behavior.

**Kill switch:** the production kill-switch runbook lives in [`api/CLAUDE.md`](../api/CLAUDE.md) under `Feature Flags → Feature flag kill-switch`.

## Layout Troubleshooting

When debugging layout issues (centered content, unexpected spacing, etc.):

1. **Check App.css first** - Default Vite templates include problematic global styles
2. **Inspect CSS cascade** - Use browser DevTools to see which styles are being applied
3. **Look for container constraints**:
   - `max-w-*` classes that limit width
   - `mx-auto` that centers content
   - `text-center` that centers text alignment
4. **Verify padding calculations** - The Layout components calculate padding based on sidebar widths:
   - IconNavigation: `w-14` (3.5rem = 56px)
   - ContextSidebar collapsed: `w-16` (4rem = 64px)
   - ContextSidebar expanded: `w-80` (20rem = 320px)
   - Total when collapsed: 120px (7.5rem)
   - Total when expanded: 376px (23.5rem)

## Important Notes

1. **SPA Architecture**: This is a client-side rendered application
2. **Authentication**: Always check auth state before protected operations
3. **UI Library**: Check existing components before creating new ones
4. **TypeScript**: Strict mode is OFF (`strict: false`, `noImplicitAny: false` in `tsconfig.app.json`). Add type annotations where practical but the compiler won't catch implicit any or null errors.
5. **Performance**: Monitor bundle size and implement code splitting for large features

---

For general coding standards, testing practices, and project-wide guidelines, refer to the [root CLAUDE.md](../CLAUDE.md) file.
