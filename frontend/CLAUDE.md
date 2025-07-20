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

## Component Development Guide

### UI Component Library

The project includes ~50 pre-built UI components in `src/components/ui/`:

**Layout Components:**

- `Card`, `Separator`, `ScrollArea`

**Form Components:**

- `Button`, `Input`, `Textarea`, `Select`
- `Checkbox`, `RadioGroup`, `Switch`
- `Form` (React Hook Form integration)

**Feedback Components:**

- `Alert`, `Toast`, `Progress`
- `Skeleton` (loading states)

**Overlay Components:**

- `Dialog`, `Sheet`, `Popover`, `Tooltip`
- `DropdownMenu`, `ContextMenu`

**Data Display:**

- `Table`, `DataTable` (with TanStack Table)
- `Badge`, `Avatar`

**Navigation:**

- `Tabs`, `NavigationMenu`, `Breadcrumb`

### Creating New Components

Follow this pattern for new components:

```tsx
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const componentVariants = cva("base classes here", {
  variants: {
    variant: {
      default: "default classes",
      secondary: "secondary classes",
    },
    size: {
      sm: "small classes",
      md: "medium classes",
      lg: "large classes",
    },
  },
  defaultVariants: {
    variant: "default",
    size: "md",
  },
});

export interface ComponentProps
  extends React.HTMLAttributes<HTMLElement>,
    VariantProps<typeof componentVariants> {
  // Additional props here
}

export const Component = React.forwardRef<HTMLElement, ComponentProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <element
        ref={ref}
        className={cn(componentVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Component.displayName = "Component";
```

## State Management Patterns

### Authentication State

```tsx
import { useAuth } from "@/contexts/AuthContext";

function MyComponent() {
  const { user, selectedOrganization, selectedAccount, signOut } = useAuth();

  if (!user) {
    return <Navigate to="/login" />;
  }

  // Component logic
}
```

### Server State with TanStack Query

```tsx
import { useQuery, useMutation } from "@tanstack/react-query";

// GET request
const { data, isLoading, error } = useQuery({
  queryKey: ["metrics", organizationId],
  queryFn: () => api.getMetrics(organizationId),
  staleTime: 5 * 60 * 1000, // 5 minutes
});

// POST/PUT/DELETE
const mutation = useMutation({
  mutationFn: (data: CreateMetricDto) => api.createMetric(data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["metrics"] });
    toast({ title: "Success", description: "Metric created" });
  },
  onError: (error) => {
    toast({
      title: "Error",
      description: error.message,
      variant: "destructive",
    });
  },
});
```

### Form State with React Hook Form

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

const formSchema = z.object({
  name: z.string().min(2).max(50),
  email: z.string().email(),
  role: z.enum(["admin", "user"]),
});

function MyForm() {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      email: "",
      role: "user",
    },
  });

  async function onSubmit(values: z.infer<typeof formSchema>) {
    // Handle form submission
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {/* Other fields */}
      </form>
    </Form>
  );
}
```

## API Integration

### Axios Configuration

```tsx
// src/lib/api.ts
import axios from "axios";
import { auth } from "@/lib/firebase";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

// Request interceptor for auth
api.interceptors.request.use(async (config) => {
  const token = await auth.currentUser?.getIdToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
    }
    return Promise.reject(error);
  },
);
```

### Type-Safe API Calls

```tsx
// src/types/api.ts
export interface Metric {
  id: string;
  name: string;
  value: number;
  organizationId: string;
}

// src/services/metrics.ts
export const metricsApi = {
  getAll: (orgId: string) =>
    api.get<Metric[]>(`/metrics?organizationId=${orgId}`),

  getById: (id: string) => api.get<Metric>(`/metrics/${id}`),

  create: (data: CreateMetricDto) => api.post<Metric>("/metrics", data),

  update: (id: string, data: UpdateMetricDto) =>
    api.put<Metric>(`/metrics/${id}`, data),

  delete: (id: string) => api.delete(`/metrics/${id}`),
};
```

## Testing Guidelines

### Component Testing

```tsx
import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("Button", () => {
  test("renders with correct text", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button")).toHaveTextContent("Click me");
  });

  test("handles click events", async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();

    render(<Button onClick={handleClick}>Click me</Button>);
    await user.click(screen.getByRole("button"));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### Testing Utilities

```tsx
// src/test/utils.tsx
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

export function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>,
  );
}
```

## Performance Optimization

### Code Splitting

```tsx
import { lazy, Suspense } from 'react'

// Lazy load heavy components
const Dashboard = lazy(() => import('./pages/Dashboard'))

// In your routes
<Route
  path="/dashboard"
  element={
    <Suspense fallback={<LoadingSpinner />}>
      <Dashboard />
    </Suspense>
  }
/>
```

### Memoization

```tsx
import { memo, useMemo, useCallback } from "react";

// Memoize expensive components
export const ExpensiveComponent = memo(({ data }) => {
  // Component logic
});

// Memoize expensive calculations
const processedData = useMemo(() => {
  return heavyDataProcessing(rawData);
}, [rawData]);

// Memoize callbacks
const handleClick = useCallback(
  (id: string) => {
    // Handle click
  },
  [dependencies],
);
```

## Common Patterns & Solutions

### Layout Troubleshooting

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

### Loading States

```tsx
function DataComponent() {
  const { data, isLoading } = useQuery(...)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    )
  }

  return <DataDisplay data={data} />
}
```

### Error Boundaries

```tsx
import { ErrorBoundary } from "react-error-boundary";

function ErrorFallback({ error, resetErrorBoundary }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>Something went wrong</AlertTitle>
      <AlertDescription>{error.message}</AlertDescription>
      <Button onClick={resetErrorBoundary}>Try again</Button>
    </Alert>
  );
}

// Wrap components
<ErrorBoundary FallbackComponent={ErrorFallback}>
  <YourComponent />
</ErrorBoundary>;
```

### Infinite Scroll

```tsx
import { useInfiniteQuery } from "@tanstack/react-query";
import { useInView } from "react-intersection-observer";

function InfiniteList() {
  const { ref, inView } = useInView();

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery({
      queryKey: ["items"],
      queryFn: ({ pageParam = 0 }) => fetchItems({ page: pageParam }),
      getNextPageParam: (lastPage, pages) => lastPage.nextPage,
    });

  React.useEffect(() => {
    if (inView && hasNextPage) {
      fetchNextPage();
    }
  }, [inView, fetchNextPage, hasNextPage]);

  return (
    <div>
      {data?.pages.map((page) =>
        page.items.map((item) => <Item key={item.id} {...item} />),
      )}
      <div ref={ref}>{isFetchingNextPage && <LoadingSpinner />}</div>
    </div>
  );
}
```

## Debugging Tips

1. **React DevTools**: Use for component inspection and performance profiling
2. **Network Tab**: Monitor API calls and responses
3. **Console Logging**: Use structured logging:
   ```tsx
   console.log("[ComponentName]", { action: "fetchData", data });
   ```
4. **Error Boundaries**: Implement to catch and log component errors
5. **React Query DevTools**: Add in development for query inspection

## Important Notes

1. **SPA Architecture**: This is a client-side rendered application
2. **Authentication**: Always check auth state before protected operations
3. **UI Library**: Check existing components before creating new ones
4. **TypeScript**: Prefer strict typing despite some relaxed settings
5. **Performance**: Monitor bundle size and implement code splitting for large features

---

For general coding standards, testing practices, and project-wide guidelines, refer to the [root CLAUDE.md](../CLAUDE.md) file.
