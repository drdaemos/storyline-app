import { useAuth as useClerkAuth } from '@clerk/vue'
import { computed } from 'vue'

export const DEV_BYPASS_USER = {
  id: 'dev-local-user',
  email: 'dev-local@example.com',
  name: 'Local Dev User',
}

const isDevAuthBypassEnabled = (): boolean =>
  import.meta.env.VITE_DEV_AUTH_BYPASS === 'true'

/**
 * Composable for authentication using Clerk.
 * Provides access to the current user's JWT token for API requests.
 */
export function useAuth() {
  const bypassEnabled = isDevAuthBypassEnabled()
  const clerkAuth = bypassEnabled ? null : useClerkAuth()
  const isBypass = computed(() => isDevAuthBypassEnabled())
  const bypassSignedIn = computed(() => isBypass.value || !!clerkAuth?.isSignedIn.value)
  const bypassLoaded = computed(() => isBypass.value || !!clerkAuth?.isLoaded.value)

  /**
   * Get the current user's JWT token for API authentication.
   * Returns null if auth is not loaded, user is not signed in, or token fetch fails.
   */
  const getAuthToken = async (): Promise<string | null> => {
    if (isBypass.value) {
      return null
    }

    try {
      // Wait for Clerk to finish loading
      if (!clerkAuth?.isLoaded.value) {
        return null
      }

      // Check if user is signed in
      if (!clerkAuth.isSignedIn.value) {
        return null
      }

      // Get the JWT token - getToken is a ref in Clerk Vue, so use .value()
      const token = await clerkAuth.getToken.value()
      return token
    } catch (error) {
      console.error('Failed to get auth token:', error)
      return null
    }
  }

  return {
    getAuthToken,
    isSignedIn: bypassSignedIn,
    isLoaded: bypassLoaded,
    isDevAuthBypassEnabled: isBypass,
    devBypassUser: DEV_BYPASS_USER,
  }
}
