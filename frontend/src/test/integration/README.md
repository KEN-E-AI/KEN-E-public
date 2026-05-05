# Integration Tests

This directory contains comprehensive integration tests for the KEN-E frontend application. These tests validate complete user workflows and ensure all components work together correctly.

## Test Structure

### Test Files

1. **`account-management-workflow.test.tsx`** - Organization and account management
2. **`account-creation-marketing-fields.test.tsx`** - Account creation form and marketing fields
3. **`index.test.tsx`** - Test suite orchestration

### Test Categories

#### Account Management Tests

- Organization settings display
- Organization update workflow
- Account creation wizard
- Account management features
- Danger zone operations
- Permission-based access control
- Data persistence and state management

#### Account Creation Tests

- Account creation form validation
- Marketing fields configuration
- Form submission workflows

## Running Tests

### Run All Integration Tests

```bash
npm run test:integration
```

### Run Specific Test Suite

```bash
npm run vitest src/test/integration/account-management-workflow.test.tsx
```

### Run with Coverage

```bash
npm run test:integration -- --coverage
```

### Run in Watch Mode

```bash
npm run test:integration -- --watch
```

## Test Patterns

### User-Centric Testing

Tests are written from the user's perspective, simulating real user interactions:

```typescript
test("should complete user profile update workflow", async () => {
  const user = userEvent.setup();

  // Simulate user actions
  await user.type(screen.getByPlaceholderText("First Name"), "John");
  await user.click(screen.getByText("Save Changes"));

  // Verify expected outcome
  expect(screen.getByText("Profile updated successfully")).toBeInTheDocument();
});
```

### Error Scenario Testing

Comprehensive error handling validation:

```typescript
test("should handle API errors gracefully", async () => {
  // Mock API error
  mockAxios.get.mockRejectedValue(new Error("Network error"));

  // Trigger action that uses API
  await user.click(screen.getByText("Load Data"));

  // Verify error handling
  expect(screen.getByText("Error loading data")).toBeInTheDocument();
});
```

### State Management Integration

Testing complex state interactions:

```typescript
test("should maintain form state during navigation", async () => {
  // Fill form
  await user.type(screen.getByPlaceholderText("Organization Name"), "Test Org");

  // Navigate away and back
  await user.click(screen.getByText("Other Page"));
  await user.click(screen.getByText("Back"));

  // Verify state persistence
  expect(screen.getByDisplayValue("Test Org")).toBeInTheDocument();
});
```

## Mock Data Strategy

### Realistic Mock Data

All tests use realistic mock data that reflects actual application usage:

```typescript
const mockUser = {
  id: "user-123",
  firstName: "John",
  lastName: "Doe",
  email: "john.doe@example.com",
  permissions: {
    organizations: {
      "org-123": "admin",
    },
  },
};
```

### Comprehensive Organization Data

Mock data includes all necessary organization structure:

```typescript
const mockOrgMetadata = {
  "org-123": {
    organization_id: "org-123",
    organization_name: "Test Organization",
    subscription: {
      /* full subscription data */
    },
    billing: {
      /* billing information */
    },
    team: {
      /* team data */
    },
  },
};
```

## Test Environment Setup

### Test Wrapper Component

Standardized test wrapper for all tests:

```typescript
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthContext.Provider value={mockAuthContext}>
          {children}
        </AuthContext.Provider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};
```

### Mock Configuration

Comprehensive mocking strategy:

```typescript
beforeEach(() => {
  vi.clearAllMocks();

  // Mock API calls
  vi.mock("axios", () => ({
    default: {
      get: vi.fn().mockResolvedValue({ data: {} }),
      post: vi.fn().mockResolvedValue({ data: {} }),
      put: vi.fn().mockResolvedValue({ data: {} }),
    },
  }));
});
```

## Best Practices

### Test Organization

- Group related tests in describe blocks
- Use descriptive test names that explain the user workflow
- Follow AAA pattern (Arrange, Act, Assert)
- Include both happy path and error scenarios

### User Interactions

- Use `userEvent` for realistic user interactions
- Wait for asynchronous operations with `waitFor`
- Test accessibility features (keyboard navigation, screen readers)
- Verify loading states and error messages

### Assertions

- Use semantic queries (`getByRole`, `getByText`, `getByLabelText`)
- Verify complete user workflows, not just component rendering
- Test data persistence and state management
- Validate error handling and recovery

### Performance

- Use realistic data volumes
- Test with slow network conditions
- Verify loading states and skeleton screens
- Test memory leaks and cleanup

## Debugging Integration Tests

### Common Issues

1. **Async Operations**: Always use `waitFor` for async operations
2. **Mock Timing**: Ensure mocks are set up before rendering
3. **State Cleanup**: Clear mocks and state between tests
4. **Error Boundaries**: Test error boundary behavior

### Debugging Tips

```typescript
// Add debug helpers
import { screen } from "@testing-library/react";

// Debug DOM structure
screen.debug();

// Log specific elements
console.log(screen.getByTestId("my-element"));

// Use findBy queries for async elements
const element = await screen.findByText("Loading complete");
```

## Continuous Integration

### Test Execution

Integration tests are automatically run in CI/CD pipeline:

- On pull requests
- Before deployment
- As part of the test suite

### Test Reports

- Coverage reports generated
- Test results published
- Performance metrics tracked

### Test Maintenance

- Regular review of test effectiveness
- Update tests when features change
- Monitor test execution time
- Maintain test data consistency

## Contributing

### Adding New Tests

1. Follow existing test patterns
2. Use realistic mock data
3. Include error scenarios
4. Test complete user workflows
5. Add appropriate documentation

### Test Review Checklist

- [ ] Tests cover complete user workflows
- [ ] Error scenarios are tested
- [ ] Mock data is realistic
- [ ] Tests are maintainable
- [ ] Performance is acceptable
- [ ] Documentation is updated
