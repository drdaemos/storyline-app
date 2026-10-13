import { setTokenProvider } from './auth'
import {
  ApiError,
  clearConversation,
  createStory,
  interrupt,
  listLore,
  listStories,
  readLore,
  readScript,
  sendPrompt,
  setModel,
  undoLastTurn,
} from './client'

interface Call {
  url: string
  method: string
  headers: Record<string, string>
  body: unknown
}

function mockFetch(respond: () => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({
        url,
        method: init.method ?? 'GET',
        headers: init.headers as Record<string, string>,
        body: typeof init.body === 'string' ? JSON.parse(init.body) : undefined,
      })
      return respond()
    })
  )
  return calls
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.unstubAllGlobals()
  setTokenProvider(null)
})

describe('API client', () => {
  it('lists stories', async () => {
    const calls = mockFetch(() => json({ stories: ['a'], active: 'a' }))
    expect(await listStories()).toEqual({ stories: ['a'], active: 'a' })
    expect(calls[0]).toMatchObject({ url: '/api/stories', method: 'GET' })
  })

  it('creates a story', async () => {
    const calls = mockFetch(() => json({ name: 'tale' }, 201))
    expect(await createStory('tale')).toEqual({ name: 'tale' })
    expect(calls[0]).toMatchObject({ url: '/api/stories', method: 'POST', body: { name: 'tale' } })
  })

  it('sends a prompt, interrupts, sets the model and clears, on the right routes', async () => {
    const calls = mockFetch(() => new Response(null, { status: 204 }))
    await sendPrompt('a tale', 'Hello')
    await interrupt('a tale')
    await setModel('a tale', 'muse-2')
    await clearConversation('a tale')
    expect(calls.map(({ url, method, body }) => ({ url, method, body }))).toEqual([
      { url: '/api/stories/a%20tale/prompts', method: 'POST', body: { text: 'Hello' } },
      { url: '/api/stories/a%20tale/interrupt', method: 'POST', body: undefined },
      { url: '/api/stories/a%20tale/model', method: 'PUT', body: { model_name: 'muse-2' } },
      { url: '/api/stories/a%20tale/clear', method: 'POST', body: undefined },
    ])
  })

  it('undoes the last turn and reports whether anything was undone', async () => {
    const calls = mockFetch(() => json({ undone: false }))
    expect(await undoLastTurn('tale')).toEqual({ undone: false })
    expect(calls[0]).toMatchObject({ url: '/api/stories/tale/undo', method: 'POST' })
  })

  it('reads the script and the lore, encoding every name', async () => {
    const calls = mockFetch(() => json({ text: '', files: [], filename: 'x' }))
    await readScript('a/b')
    await listLore('a/b')
    await readLore('a/b', 'the station?.md')
    expect(calls.map((call) => call.url)).toEqual([
      '/api/stories/a%2Fb/script',
      '/api/stories/a%2Fb/lore',
      '/api/stories/a%2Fb/lore/the%20station%3F.md',
    ])
  })

  it('sends the session token when there is one', async () => {
    setTokenProvider(async () => 'token-1')
    const calls = mockFetch(() => json({ stories: [], active: null }))
    await listStories()
    expect(calls[0]?.headers.Authorization).toBe('Bearer token-1')
  })

  it('sends no token when there is no provider or the provider has none', async () => {
    const calls = mockFetch(() => json({ stories: [], active: null }))
    await listStories()
    setTokenProvider(async () => null)
    await listStories()
    expect(calls[0]?.headers.Authorization).toBeUndefined()
    expect(calls[1]?.headers.Authorization).toBeUndefined()
  })

  it('raises the detail the server gave, with the status', async () => {
    mockFetch(() => json({ detail: 'That name is taken.' }, 400))
    await expect(createStory('tale')).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
      message: 'That name is taken.',
    })
  })

  it('joins validation messages when the detail is a list', async () => {
    mockFetch(() => json({ detail: [{ msg: 'Too short' }, { msg: 'Bad characters' }] }, 422))
    await expect(createStory('x')).rejects.toThrow('Too short; Bad characters')
  })

  it('still raises something readable when the body is not JSON', async () => {
    mockFetch(() => new Response('Bad gateway', { status: 502 }))
    const error = await listStories().catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe('The server answered 502.')
  })

  it('raises an error when the server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(listStories()).rejects.toMatchObject({ status: 0, message: 'Could not reach the server.' })
  })
})
