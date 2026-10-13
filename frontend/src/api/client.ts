/** One function per protocol operation, over the HTTP API. */
import type { Operation, LoreFileSummary, StoryList } from '@/protocol/types'
import { authHeaders } from './auth'
import { connectRoomStream } from './sse'
import type { RoomStream, RoomStreamHandlers, RoomStreamOptions } from './sse'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function describeError(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}

const API_ROOT = '/api'

function storyPath(story: string, rest = ''): string {
  return `${API_ROOT}/stories/${encodeURIComponent(story)}${rest}`
}

function detailOf(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string' && detail) return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (typeof item === 'object' && item !== null ? (item as { msg?: unknown }).msg : null))
        .filter((message): message is string => typeof message === 'string')
      if (messages.length > 0) return messages.join('; ')
    }
  }
  if (status === 401) return 'You are signed out.'
  return `The server answered ${status}.`
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...(await authHeaders()) }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Could not reach the server.')
  }
  const text = await response.text()
  let parsed: unknown
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = undefined
    }
  }
  if (!response.ok) throw new ApiError(response.status, detailOf(parsed, response.status))
  return parsed as T
}

export function listStories(): Promise<StoryList> {
  return request('GET', `${API_ROOT}/stories`)
}

export function createStory(name: string): Promise<{ name: string }> {
  return request('POST', `${API_ROOT}/stories`, { name })
}

export function openStory(
  story: string,
  handlers: RoomStreamHandlers,
  options?: RoomStreamOptions
): RoomStream {
  return connectRoomStream(story, handlers, options)
}

export async function sendPrompt(story: string, text: string): Promise<void> {
  await request('POST', storyPath(story, '/prompts'), { text })
}

export async function interrupt(story: string): Promise<void> {
  await request('POST', storyPath(story, '/interrupt'))
}

export async function setModel(story: string, modelName: string): Promise<void> {
  await request('PUT', storyPath(story, '/model'), { model_name: modelName })
}

export function undoLastTurn(story: string): Promise<{ undone: boolean }> {
  return request('POST', storyPath(story, '/undo'))
}

export async function clearConversation(story: string): Promise<void> {
  await request('POST', storyPath(story, '/clear'))
}

export function readScript(story: string): Promise<{ text: string }> {
  return request('GET', storyPath(story, '/script'))
}

export function listLore(story: string): Promise<{ files: LoreFileSummary[] }> {
  return request('GET', storyPath(story, '/lore'))
}

export function readLore(story: string, filename: string): Promise<{ filename: string; text: string }> {
  return request('GET', storyPath(story, `/lore/${encodeURIComponent(filename)}`))
}

/** Every operation of the protocol; `parity.test.ts` fails when one is missing. */
export const OPERATION_CLIENT: Record<Operation, (...args: never[]) => unknown> = {
  list_stories: listStories,
  create_story: createStory,
  open_story: openStory,
  send_prompt: sendPrompt,
  interrupt,
  set_model: setModel,
  undo_last_turn: undoLastTurn,
  clear_conversation: clearConversation,
  read_script: readScript,
  list_lore: listLore,
  read_lore: readLore,
}
