import { setTokenProvider } from './auth'
import { SseParser, connectRoomStream, routeMessage, streamUrl } from './sse'
import type { RoomStreamHandlers, StreamStatus } from './sse'
import type { RoomEvent, RoomSnapshot } from '@/protocol/types'

describe('SseParser', () => {
  it('parses a message with an event name and data', () => {
    const parser = new SseParser()
    expect(parser.feed('event: reply_delta\ndata: {"a":1}\n\n')).toEqual([
      { event: 'reply_delta', data: '{"a":1}' },
    ])
  })

  it('waits for the blank line before it emits', () => {
    const parser = new SseParser()
    expect(parser.feed('event: notice\ndata: x\n')).toEqual([])
    expect(parser.feed('\n')).toEqual([{ event: 'notice', data: 'x' }])
  })

  it('joins chunks that split a line, a field name and a message', () => {
    const parser = new SseParser()
    const wire = 'event: snapshot\ndata: {"story":"a"}\n\nevent: notice\ndata: {"b":2}\n\n'
    const messages = [...wire].flatMap((char) => parser.feed(char))
    expect(messages).toEqual([
      { event: 'snapshot', data: '{"story":"a"}' },
      { event: 'notice', data: '{"b":2}' },
    ])
  })

  it('joins several data lines with a newline', () => {
    const parser = new SseParser()
    expect(parser.feed('data: one\ndata: two\ndata:three\n\n')).toEqual([
      { event: 'message', data: 'one\ntwo\nthree' },
    ])
  })

  it('ignores comment lines, including keepalives between messages', () => {
    const parser = new SseParser()
    const messages = parser.feed(': keepalive\n\nevent: a\n: inside\ndata: 1\n\n: keepalive\n\n')
    expect(messages).toEqual([{ event: 'a', data: '1' }])
  })

  it('does not emit a message that has no data', () => {
    const parser = new SseParser()
    expect(parser.feed('event: lonely\n\n')).toEqual([])
    expect(parser.feed('data: next\n\n')).toEqual([{ event: 'message', data: 'next' }])
  })

  it('accepts CRLF and bare CR line endings, even when CR and LF are split across chunks', () => {
    const parser = new SseParser()
    expect(parser.feed('event: a\r\ndata: 1\r\n\r\n')).toEqual([{ event: 'a', data: '1' }])
    expect(parser.feed('event: b\rdata: 2\r\r')).toEqual([{ event: 'b', data: '2' }])
    expect(parser.feed('event: c\r')).toEqual([])
    expect(parser.feed('\ndata: 3\r')).toEqual([])
    expect(parser.feed('\n\r\n')).toEqual([{ event: 'c', data: '3' }])
  })

  it('strips one leading space from a value and keeps the rest', () => {
    const parser = new SseParser()
    expect(parser.feed('data:  two spaces\n\n')).toEqual([{ event: 'message', data: ' two spaces' }])
  })

  it('keeps a colon inside a value', () => {
    const parser = new SseParser()
    expect(parser.feed('data: {"a":"b:c"}\n\n')).toEqual([{ event: 'message', data: '{"a":"b:c"}' }])
  })

  it('starts each message with an empty event name', () => {
    const parser = new SseParser()
    parser.feed('event: first\ndata: 1\n\n')
    expect(parser.feed('data: 2\n\n')).toEqual([{ event: 'message', data: '2' }])
  })
})

function recorder() {
  const snapshots: RoomSnapshot[] = []
  const events: RoomEvent[] = []
  const statuses: StreamStatus[] = []
  const handlers: RoomStreamHandlers = {
    onSnapshot: (snapshot) => snapshots.push(snapshot),
    onEvent: (event) => events.push(event),
    onStatus: (status) => statuses.push(status),
  }
  return { snapshots, events, statuses, handlers }
}

describe('routeMessage', () => {
  it('sends a snapshot message to onSnapshot', () => {
    const seen = recorder()
    const isSnapshot = routeMessage({ event: 'snapshot', data: '{"story":"a"}' }, seen.handlers)
    expect(isSnapshot).toBe(true)
    expect(seen.snapshots).toEqual([{ story: 'a' }])
  })

  it('sends a known event to onEvent and drops unknown ones and bad JSON', () => {
    const seen = recorder()
    routeMessage({ event: 'notice', data: '{"type":"notice","level":"info","text":"hi"}' }, seen.handlers)
    routeMessage({ event: 'mystery', data: '{"type":"mystery"}' }, seen.handlers)
    routeMessage({ event: 'notice', data: 'not json' }, seen.handlers)
    expect(seen.events).toEqual([{ type: 'notice', level: 'info', text: 'hi' }])
  })
})

function streamOf(...chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

const SNAPSHOT = 'event: snapshot\ndata: {"story":"tale","entries":[]}\n\n'

describe('connectRoomStream', () => {
  afterEach(() => setTokenProvider(null))

  it('encodes the story name in the URL', () => {
    expect(streamUrl('a b/c')).toBe('/api/stories/a%20b%2Fc/events')
  })

  it('delivers the snapshot and the events that follow it, split anywhere', async () => {
    const seen = recorder()
    const wire = `${SNAPSHOT}: keepalive\n\nevent: notice\ndata: {"type":"notice","level":"info","text":"hello"}\n\n`
    const cut = 37
    let calls = 0
    const stream = connectRoomStream('tale', seen.handlers, {
      fetchImpl: async () => {
        calls++
        if (calls > 1) return new Promise<Response>(() => undefined)
        return streamOf(wire.slice(0, cut), wire.slice(cut))
      },
      sleep: () => new Promise(() => undefined),
    })
    await vi.waitFor(() => expect(seen.events).toHaveLength(1))
    stream.close()
    expect(seen.snapshots).toHaveLength(1)
    expect(seen.events[0]).toMatchObject({ type: 'notice', text: 'hello' })
    expect(seen.statuses.slice(0, 2)).toEqual(['connecting', 'open'])
  })

  it('sends the bearer token when there is a provider, and none otherwise', async () => {
    setTokenProvider(async () => 'secret')
    const headers: Array<HeadersInit | undefined> = []
    const seen = recorder()
    const stream = connectRoomStream('tale', seen.handlers, {
      fetchImpl: async (_url, init) => {
        headers.push(init?.headers)
        return new Promise<Response>(() => undefined)
      },
    })
    await vi.waitFor(() => expect(headers).toHaveLength(1))
    stream.close()
    expect(headers[0]).toMatchObject({ Authorization: 'Bearer secret', Accept: 'text/event-stream' })
  })

  it('reconnects after the connection ends, and the new snapshot is delivered again', async () => {
    const seen = recorder()
    const sleeps: number[] = []
    let calls = 0
    const stream = connectRoomStream('tale', seen.handlers, {
      initialDelay: 100,
      fetchImpl: async () => {
        calls++
        if (calls <= 2) return streamOf(SNAPSHOT)
        return new Promise<Response>(() => undefined)
      },
      sleep: async (milliseconds) => {
        sleeps.push(milliseconds)
      },
    })
    await vi.waitFor(() => expect(seen.snapshots).toHaveLength(2))
    stream.close()
    expect(seen.statuses).toContain('reconnecting')
    // A connection that delivered a snapshot starts the delay over.
    expect(sleeps.slice(0, 2)).toEqual([100, 100])
  })

  it('backs off while the server cannot be reached', async () => {
    const seen = recorder()
    const sleeps: number[] = []
    let calls = 0
    const stream = connectRoomStream('tale', seen.handlers, {
      initialDelay: 100,
      maxDelay: 350,
      fetchImpl: async () => {
        calls++
        if (calls <= 4) throw new TypeError('offline')
        return new Promise<Response>(() => undefined)
      },
      sleep: async (milliseconds) => {
        sleeps.push(milliseconds)
      },
    })
    await vi.waitFor(() => expect(calls).toBe(5))
    stream.close()
    expect(sleeps).toEqual([100, 200, 350, 350])
  })

  it('stops, and says why, when the story does not exist', async () => {
    const statuses: Array<[StreamStatus, string | undefined]> = []
    let calls = 0
    connectRoomStream(
      'ghost',
      {
        onSnapshot: () => undefined,
        onEvent: () => undefined,
        onStatus: (status, detail) => statuses.push([status, detail]),
      },
      {
        fetchImpl: async () => {
          calls++
          return new Response(JSON.stringify({ detail: 'No such story.' }), { status: 404 })
        },
        sleep: () => new Promise(() => undefined),
      }
    )
    await vi.waitFor(() => expect(statuses.at(-1)).toEqual(['failed', 'No such story.']))
    expect(calls).toBe(1)
  })
})
