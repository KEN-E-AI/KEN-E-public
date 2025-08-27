/**
 * Auth Recovery Utility
 * Helps recover from corrupted auth state after account/org deletion
 */

import { auth } from "@/lib/firebase";

export interface AuthRecoveryResult {
  success: boolean;
  message: string;
  clearedItems: string[];
}

/**
 * Validates and cleans corrupted auth state
 * This should be called when the app detects invalid state
 */
export async function validateAndCleanAuthState(): Promise<AuthRecoveryResult> {
  const clearedItems: string[] = [];
  
  try {
    // Check if we have a valid Firebase user
    const currentUser = auth.currentUser;
    
    // Get all auth-related localStorage items
    const authKeys = [
      'selectedOrgAccount',
      'currentOrganizationId',
      'hasSelectedWorkspace',
      'orgMetadata',
      'accountMetadata',
      'user'
    ];
    
    // Check for corrupted data
    for (const key of authKeys) {
      const value = localStorage.getItem(key);
      if (value) {
        try {
          // Try to parse JSON values
          if (key !== 'hasSelectedWorkspace' && key !== 'currentOrganizationId') {
            const parsed = JSON.parse(value);
            
            // Check for undefined or invalid structures
            if (!parsed || 
                (key === 'selectedOrgAccount' && (!parsed.orgId || !parsed.accountId)) ||
                (key === 'user' && !parsed.id)) {
              localStorage.removeItem(key);
              clearedItems.push(key);
            }
          }
        } catch (e) {
          // If parsing fails, remove the corrupted item
          localStorage.removeItem(key);
          clearedItems.push(key);
        }
      }
    }
    
    // If we cleared critical items, reset workspace selection
    if (clearedItems.includes('selectedOrgAccount') || 
        clearedItems.includes('currentOrganizationId')) {
      localStorage.removeItem('hasSelectedWorkspace');
      clearedItems.push('hasSelectedWorkspace');
    }
    
    return {
      success: true,
      message: clearedItems.length > 0 
        ? `Cleared corrupted auth data: ${clearedItems.join(', ')}`
        : 'Auth state is valid',
      clearedItems
    };
    
  } catch (error) {
    console.error('Error during auth recovery:', error);
    
    // Nuclear option: clear everything
    localStorage.clear();
    
    return {
      success: false,
      message: 'Complete auth state reset performed',
      clearedItems: ['all']
    };
  }
}

/**
 * Check if the current auth state references deleted entities
 * This should be called on app initialization
 */
export async function checkForDeletedEntities(): Promise<boolean> {
  try {
    const savedOrgAccount = localStorage.getItem('selectedOrgAccount');
    if (!savedOrgAccount) return false;
    
    const parsed = JSON.parse(savedOrgAccount);
    
    // TODO: Make API call to verify these entities still exist
    // For now, just check if the structure is valid
    return !parsed.orgId || !parsed.accountId;
    
  } catch (error) {
    return true; // If we can't parse, consider it invalid
  }
}

/**
 * Force a clean logout and redirect to login
 */
export async function forceCleanLogout(): Promise<void> {
  try {
    // Clear all localStorage
    localStorage.clear();
    
    // Sign out from Firebase
    await auth.signOut();
    
    // Force redirect to login
    window.location.href = '/auth/signin';
  } catch (error) {
    console.error('Error during force logout:', error);
    // Even if Firebase signout fails, still redirect
    window.location.href = '/auth/signin';
  }
}