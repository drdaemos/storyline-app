/// <reference types="vite/client" />

interface ViteTypeOptions {
  // By adding this line, you can make the type of ImportMetaEnv strict
  // to disallow unknown keys.
  // strictImportMetaEnv: unknown
}

interface ImportMetaEnv {
  readonly VITE_APP_TITLE: string
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
  readonly VITE_DEV_AUTH_BYPASS?: 'true' | 'false'
  // more env variables...
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
