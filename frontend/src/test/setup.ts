import { vi } from "vitest";
import "@testing-library/jest-dom";

// Mock import.meta.env globally for all tests
vi.stubEnv("VITE_API_BASE_URL", "http://test-api.com");

// Ensure fetch is mocked globally
global.fetch = vi.fn();

// TODO(test-env-node25): Node 25's partial built-in localStorage leaks into the jsdom
// environment as an empty object (no methods, not an instanceof Storage). Replace it
// with a Storage-shape in-memory stub branded against jsdom's Storage class so the
// StorageEvent constructor's storageArea brand check still passes. Remove this once the
// test env is fixed (pin Node 22 LTS or upgrade jsdom).
// See LAYOUT-HORIZONTAL-NAV-REFACTOR-PLAN.md §10.1.
const localStorageStore = new Map<string, string>();
const localStorageStub = Object.create(Storage.prototype) as Storage;
Object.defineProperties(localStorageStub, {
  length: { get: () => localStorageStore.size },
  clear: { value: () => localStorageStore.clear() },
  getItem: { value: (key: string) => localStorageStore.get(key) ?? null },
  setItem: {
    value: (key: string, value: string) => {
      localStorageStore.set(key, String(value));
    },
  },
  removeItem: {
    value: (key: string) => {
      localStorageStore.delete(key);
    },
  },
  key: {
    value: (index: number) =>
      Array.from(localStorageStore.keys())[index] ?? null,
  },
});
Object.defineProperty(window, "localStorage", {
  value: localStorageStub,
  writable: true,
  configurable: true,
});

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
