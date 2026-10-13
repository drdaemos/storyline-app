/**
 * Server-sent events read with `fetch`, because the stream needs a bearer header and `EventSource`
 * cannot send one. `SseParser` is pure; `connectRoomStream` adds reconnecting around it.
 */
import { isRoomEvent } from '@/protocol/types'
import type { RoomEvent, RoomSnapshot } from '@/protocol/types'
import { authHeaders } from './auth'

export interface SseMessage {
  event: string
  data: string
}

/** Incremental parser for the `text/event-stream` format; chunks may split anywhere. */
export class SseParser {
  private buffer = ''
  private pendingCarriageReturn = false
  private event = ''
  private data: string[] = []
  private hasData = false

  feed(chunk: string): SseMessage[] {
    let text = this.buffer + chunk
    this.buffer = ''
    if (this.pendingCarriageReturn && text.startsWith('\n')) text = text.slice(1)
    this.pendingCarriageReturn = false
    const messages: SseMessage[] = []
    let start = 0
    let index = 0
    while (index < text.length) {
      const char = text[index]
      if (char !== '\n' && char !== '\r') {
        index++
        continue
      }
      const message = this.line(text.slice(start, index))
      if (message) messages.push(message)
      index += this.breakLength(text, index)
      start = index
    }
    this.buffer = text.slice(start)
    return messages
  }

  /** A line ends with LF, CR or CRLF; a CR at the end of a chunk may be the first half of a CRLF. */
  private breakLength(text: string, index: number): number {
    if (text[index] !== '\r') return 1
    if (text[index + 1] === '\n') return 2
    if (index + 1 === text.length) this.pendingCarriageReturn = true
    return 1
  }

  private line(line: string): SseMessage | null {
    if (line === '') return this.dispatch()
    if (line.startsWith(':')) return null
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') this.event = value
    else if (field === 'data') {
      this.data.push(value)
      this.hasData = true
    }
    return null
  }

  private dispatch(): SseMessage | null {
    const message = this.hasData ? { event: this.event || 'message', data: this.data.join('\n') } : null
    this.event = ''
    this.data = []
    this.hasData = false
    return message
  }
}

export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'failed'

export interface RoomStreamHandlers {
  onSnapshot(snapshot: RoomSnapshot): void
  onEvent(event: RoomEvent): void
  onStatus(status: StreamStatus, detail?: string): void
}

export interface RoomStreamOptions {
  fetchImpl?: typeof fetch
  sleep?: (milliseconds: number, signal: AbortSignal) => Promise<void>
  initialDelay?: number
  maxDelay?: number
}

export interface RoomStream {
  close(): void
}

/** Status codes that retrying cannot fix. */
const FATAL_STATUSES = new Set([400, 403, 404])

export function streamUrl(story: string): string {
  return `/api/stories/${encodeURIComponent(story)}/events`
}

function delay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, milliseconds)
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        resolve()
      },
      { once: true }
    )
  })
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

/** Route one parsed SSE message to the handlers; returns true when it was a snapshot. */
export function routeMessage(message: SseMessage, handlers: RoomStreamHandlers): boolean {
  const payload = parseJson(message.data)
  if (typeof payload !== 'object' || payload === null) return false
  if (message.event === 'snapshot') {
    handlers.onSnapshot(payload as RoomSnapshot)
    return true
  }
  if (isRoomEvent(payload)) handlers.onEvent(payload)
  return false
}

/**
 * Open the room's event stream and keep it open: each connection starts with a snapshot that
 * replaces the room state, and a dropped connection is retried with a growing delay.
 */
export function connectRoomStream(
  story: string,
  handlers: RoomStreamHandlers,
  options: RoomStreamOptions = {}
): RoomStream {
  const fetchImpl = options.fetchImpl ?? ((...args) => fetch(...args))
  const sleep = options.sleep ?? delay
  const initialDelay = options.initialDelay ?? 500
  const maxDelay = options.maxDelay ?? 10_000
  const controller = new AbortController()
  let attempt = 0

  /** Open the stream; null when the server refused it for good. */
  async function open(): Promise<ReadableStreamDefaultReader<Uint8Array> | null> {
    const headers = { Accept: 'text/event-stream', ...(await authHeaders()) }
    const response = await fetchImpl(streamUrl(story), { headers, signal: controller.signal })
    if (response.ok && response.body !== null) return response.body.getReader()
    if (!FATAL_STATUSES.has(response.status)) throw new Error(`The event stream answered ${response.status}`)
    handlers.onStatus('failed', await failureDetail(response))
    return null
  }

  async function pump(reader: ReadableStreamDefaultReader<Uint8Array>): Promise<void> {
    const decoder = new TextDecoder()
    const parser = new SseParser()
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) return
        for (const message of parser.feed(decoder.decode(value, { stream: true }))) {
          if (!routeMessage(message, handlers)) continue
          handlers.onStatus('open')
          attempt = 0
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  async function run(): Promise<void> {
    handlers.onStatus('connecting')
    while (!controller.signal.aborted) {
      try {
        const reader = await open()
        if (reader === null) return
        await pump(reader)
      } catch {
        // A dropped or refused connection is retried below.
      }
      if (controller.signal.aborted) return
      handlers.onStatus('reconnecting')
      await sleep(Math.min(maxDelay, initialDelay * 2 ** attempt), controller.signal)
      attempt++
    }
  }

  void run()
  return { close: () => controller.abort() }
}

async function failureDetail(response: Response): Promise<string> {
  const body = parseJson(await response.text().catch(() => ''))
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return `The event stream answered ${response.status}`
}
