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

// jsdom does not implement the Pointer Capture API or scrollIntoView; Radix UI
// primitives (Select, Collapsible, DropdownMenu) call these during pointer
// interactions, throwing "target.hasPointerCapture is not a function" in tests.
// Stub them on Element / HTMLElement so Radix interactions are inert in tests.
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = vi.fn().mockReturnValue(false);
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = vi.fn();
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = vi.fn();
}
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = vi.fn();
}

// Reset mocks before each test
beforeEach(() => {
  vi.clearAllMocks();
});
