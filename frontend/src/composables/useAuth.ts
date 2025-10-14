import { useAuth as useClerkAuth } from '@clerk/vue'

/**
 * Composable for authentication using Clerk.
 * Provides access to the current user's JWT token for API requests.
 */
export function useAuth() {
  const { getToken, isSignedIn, isLoaded } = useClerkAuth()

  /**
   * Get the current user's JWT token for API authentication.
   * Returns null if auth is not loaded, user is not signed in, or token fetch fails.
   */
  const getAuthToken = async (): Promise<string | null> => {
    try {
      // Wait for Clerk to finish loading
      if (!isLoaded.value) {
        return null
      }

      // Check if user is signed in
      if (!isSignedIn.value) {
        return null
      }

      // Get the JWT token - getToken is a ref in Clerk Vue, so use .value()
      const token = await getToken.value()
      return token
    } catch (error) {
      console.error('Failed to get auth token:', error)
      return null
    }
  }

  return {
    getAuthToken,
    isSignedIn,
    isLoaded
  }
}
