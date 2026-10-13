/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Clerk publishable key; without it the app runs with no sign-in and sends no token. */
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
