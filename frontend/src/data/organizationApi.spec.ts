import { describe, test, expect, vi, beforeEach } from 'vitest'
import {
  getOrganizations,
  getOrganizationById,
  createOrganization,
  updateOrganization,
  deleteOrganization,
  getAccounts,
  getAccountById,
  createAccount,
  updateAccount,
  deleteAccount,
} from './organizationApi'

describe('organizationApi', () => {
  const mockOrgId = 'test-org-123'
  const mockAccountId = 'test-account-456'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getOrganizations', () => {
    test('fetches organizations successfully', async () => {
      const mockOrganizations = [
        { organization_id: '1', organization_name: 'Org 1' },
        { organization_id: '2', organization_name: 'Org 2' },
      ]
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ organizations: mockOrganizations, total: 2 }),
      } as Response)

      const result = await getOrganizations()

      expect(fetch).toHaveBeenCalledWith('http://test-api.com/api/v1/organizations/', {
        headers: {
          'Content-Type': 'application/json',
        },
      })
      expect(result).toEqual(mockOrganizations)
    })

    test('handles empty organizations list', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ organizations: [], total: 0 }),
      } as Response)

      const result = await getOrganizations()

      expect(result).toEqual([])
    })

    test('throws error on API failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response)

      await expect(getOrganizations()).rejects.toThrow('HTTP error! status: 500')
    })
  })

  describe('getOrganizationById', () => {
    test('fetches single organization successfully', async () => {
      const mockOrg = { organization_id: mockOrgId, organization_name: 'Test Org' }
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ organization: mockOrg }),
      } as Response)

      const result = await getOrganizationById(mockOrgId)

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/organizations/${mockOrgId}`, {
        headers: {
          'Content-Type': 'application/json',
        },
      })
      expect(result).toEqual(mockOrg)
    })

    test('throws error when organization not found', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response)

      await expect(getOrganizationById(mockOrgId)).rejects.toThrow('HTTP error! status: 404')
    })
  })

  describe('createOrganization', () => {
    test('creates organization successfully', async () => {
      const newOrg = {
        organization_name: 'New Org',
        plan: 'premium',
        website: 'https://example.com',
        company_size: '50-100',
        agency: false,
        subscription: {
          plan_name: 'Premium',
          plan_description: 'Premium features',
          price: 99,
          billing_cycle: 'monthly',
          features: ['Feature 1'],
          current_period_start: new Date().toISOString(),
          current_period_end: new Date().toISOString(),
          is_active: true,
          usage: {
            insights_generated: 0,
            reports_created: 0,
            data_sources_connected: 0,
          },
        },
        billing: {
          plan: 'premium',
          status: 'active',
          next_billing_date: new Date().toISOString(),
          payment_method: 'credit_card',
        },
        team: {
          members: [],
          pending_invites: [],
        },
      }
      const createdOrg = { ...newOrg, organization_id: 'new-org-id' }
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ organization: createdOrg }),
      } as Response)

      const result = await createOrganization(newOrg)

      expect(fetch).toHaveBeenCalledWith('http://test-api.com/api/v1/organizations/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newOrg),
      })
      expect(result).toEqual(createdOrg)
    })
  })

  describe('updateOrganization', () => {
    test('updates organization successfully', async () => {
      const updateData = { organization_name: 'Updated Org' }
      const updatedOrg = { organization_id: mockOrgId, ...updateData }
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ organization: updatedOrg }),
      } as Response)

      const result = await updateOrganization(mockOrgId, updateData)

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/organizations/${mockOrgId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      })
      expect(result).toEqual(updatedOrg)
    })
  })

  describe('deleteOrganization', () => {
    test('deletes organization successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      } as Response)

      await deleteOrganization(mockOrgId)

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/organizations/${mockOrgId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    })
  })

  describe('getAccounts', () => {
    test('fetches accounts with organization filter', async () => {
      const mockAccounts = [
        { account_id: '1', account_name: 'Account 1' },
        { account_id: '2', account_name: 'Account 2' },
      ]
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ accounts: mockAccounts, total: 2 }),
      } as Response)

      const result = await getAccounts(mockOrgId)

      expect(fetch).toHaveBeenCalledWith(
        `http://test-api.com/api/v1/accounts/?organization_id=${mockOrgId}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      expect(result).toEqual(mockAccounts)
    })

    test('fetches all accounts without filter', async () => {
      const mockAccounts = [{ account_id: '1', account_name: 'Account 1' }]
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ accounts: mockAccounts, total: 1 }),
      } as Response)

      const result = await getAccounts()

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/accounts/`, {
        headers: {
          'Content-Type': 'application/json',
        },
      })
      expect(result).toEqual(mockAccounts)
    })
  })

  describe('getAccountById', () => {
    test('fetches single account successfully', async () => {
      const mockAccount = { account_id: mockAccountId, account_name: 'Test Account' }
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ account: mockAccount }),
      } as Response)

      const result = await getAccountById(mockAccountId)

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/accounts/${mockAccountId}`, {
        headers: {
          'Content-Type': 'application/json',
        },
      })
      expect(result).toEqual(mockAccount)
    })
  })

  describe('createAccount', () => {
    test('creates account successfully', async () => {
      const newAccount = {
        account_name: 'New Account',
        organization_id: mockOrgId,
        industry: 'Technology',
        status: 'Active',
        websites: ['https://example.com'],
        timezone: 'America/New_York',
      }
      const createdAccount = { ...newAccount, account_id: 'new-account-id' }
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ account: createdAccount }),
      } as Response)

      const result = await createAccount(newAccount)

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/accounts/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newAccount),
      })
      expect(result).toEqual(createdAccount)
    })
  })

  describe('updateAccount', () => {
    test('updates account successfully', async () => {
      const updateData = { account_name: 'Updated Account' }
      const updatedAccount = { account_id: mockAccountId, ...updateData }
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ account: updatedAccount }),
      } as Response)

      const result = await updateAccount(mockAccountId, updateData)

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/accounts/${mockAccountId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      })
      expect(result).toEqual(updatedAccount)
    })
  })

  describe('deleteAccount', () => {
    test('deletes account successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      } as Response)

      await deleteAccount(mockAccountId)

      expect(fetch).toHaveBeenCalledWith(`http://test-api.com/api/v1/accounts/${mockAccountId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    })
  })

  describe('Network timeout and error scenarios', () => {
    test('handles network timeout', async () => {
      // Create an AbortController to simulate timeout
      const timeoutError = new Error('The operation was aborted')
      timeoutError.name = 'AbortError'
      vi.mocked(fetch).mockRejectedValueOnce(timeoutError)

      await expect(getOrganizations()).rejects.toThrow('The operation was aborted')
    })

    test('handles network connection failure', async () => {
      const networkError = new TypeError('Failed to fetch')
      vi.mocked(fetch).mockRejectedValueOnce(networkError)

      await expect(getOrganizations()).rejects.toThrow('Failed to fetch')
    })

    test('handles partial response (connection lost)', async () => {
      // Mock a response that starts but fails during json parsing
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Unexpected end of JSON input')
        },
      } as Response)

      await expect(getOrganizations()).rejects.toThrow('Unexpected end of JSON input')
    })

    test('handles slow response with potential timeout', async () => {
      // Mock a delayed response
      vi.mocked(fetch).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => ({ organizations: [], total: 0 }),
              } as Response)
            }, 100) // 100ms delay
          })
      )

      // Should still work, just slower
      const result = await getOrganizations()
      expect(result).toEqual([])
    })

    test('handles DNS resolution failure', async () => {
      const dnsError = new Error('getaddrinfo ENOTFOUND test-api.com')
      dnsError.name = 'Error'
      vi.mocked(fetch).mockRejectedValueOnce(dnsError)

      await expect(getAccounts()).rejects.toThrow('getaddrinfo ENOTFOUND')
    })

    test('handles connection reset', async () => {
      const resetError = new Error('socket hang up')
      vi.mocked(fetch).mockRejectedValueOnce(resetError)

      await expect(createOrganization({
        organization_name: 'Test',
        plan: 'free',
        website: 'https://test.com',
        company_size: '1-50',
        agency: false,
        subscription: {} as any,
        billing: {} as any,
        team: {} as any,
      })).rejects.toThrow('socket hang up')
    })

    test('handles CORS errors', async () => {
      // CORS errors typically manifest as network errors in fetch
      const corsError = new TypeError('Failed to fetch')
      corsError.message = 'Failed to fetch'
      vi.mocked(fetch).mockRejectedValueOnce(corsError)

      await expect(updateAccount(mockAccountId, { account_name: 'Updated' })).rejects.toThrow('Failed to fetch')
    })
  })
})