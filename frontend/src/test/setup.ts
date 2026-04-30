import { vi } from "vitest";
import "@testing-library/jest-dom";

// Mock import.meta.env globally for all tests
vi.stubEnv("VITE_API_BASE_URL", "http://test-api.com");

// Ensure fetch is mocked globally
global.fetch = vi.fn();

// Mock ResizeObserver which is used by Radix UI components
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// jsdom does not implement matchMedia; stub it so components using it don't throw
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn().mockReturnValue(false),
  })),
});

// Reset mocks before each test
beforeEach(() => {
  vi.clearAllMocks();
});
