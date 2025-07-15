import { vi } from 'vitest'

// Mock import.meta.env globally for all tests
vi.stubEnv('VITE_API_BASE_URL', 'http://test-api.com')

// Ensure fetch is mocked globally
global.fetch = vi.fn()

// Reset mocks before each test
beforeEach(() => {
  vi.clearAllMocks()
})