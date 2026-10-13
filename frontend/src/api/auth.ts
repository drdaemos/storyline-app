/** Where the API client gets its bearer token. Without a provider no token is sent (local development). */

export type TokenProvider = () => Promise<string | null | undefined>

let provider: TokenProvider | null = null

export function setTokenProvider(next: TokenProvider | null): void {
  provider = next
}

export async function authHeaders(): Promise<Record<string, string>> {
  if (provider === null) return {}
  const token = await provider()
  return token ? { Authorization: `Bearer ${token}` } : {}
}
