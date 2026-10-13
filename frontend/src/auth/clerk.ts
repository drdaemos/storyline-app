/** Sign-in is on only when a Clerk key is configured; without one the app runs open, as in local development. */
export const clerkPublishableKey: string | undefined =
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim() || undefined

export const clerkEnabled: boolean = clerkPublishableKey !== undefined
