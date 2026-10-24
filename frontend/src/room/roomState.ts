/**
 * The room's state as plain data, and the pure functions that carry it forward.
 * Components read this state and call the API client; the protocol logic lives here.
 */
import type {
  Activity,
  AgendaItem,
  ArchivedConversation,
  Entry,
  EventOf,
  NoticeLevel,
  RoomEvent,
  RoomEventType,
  RoomSnapshot,
} from '@/protocol/types'

/** A line in the log that the room says rather than the writer or the user. The server never sends it as an entry. */
export interface NoticeEntry {
  kind: 'notice'
  level: NoticeLevel
  text: string
}

export type LogEntry = Entry | NoticeEntry

export interface RoomState {
  /** False until the first snapshot of the connection has arrived. */
  loaded: boolean
  story: string
  modelName: string
  modelFromStory: boolean
  entries: LogEntry[]
  hiddenEntries: number
  agenda: AgendaItem[]
  agendaError: string | null
  activity: Activity
  toolName: string | null
  queue: string[]
  archived: ArchivedConversation | null
  /** The text in the input. The room writes to it when it hands a prompt back. */
  draft: string
  /** Counters that go up when the writer changed the files shown in the book. */
  scriptRevision: number
  loreRevision: number
}

export function initialRoomState(story = ''): RoomState {
  return {
    loaded: false,
    story,
    modelName: '',
    modelFromStory: false,
    entries: [],
    hiddenEntries: 0,
    agenda: [],
    agendaError: null,
    activity: 'idle',
    toolName: null,
    queue: [],
    archived: null,
    draft: '',
    scriptRevision: 0,
    loreRevision: 0,
  }
}

export const INTERRUPTED_NOTICE = 'Interrupted.'
export const FAILED_NOTICE = 'The writer stopped because of an error.'

function archiveNotice(archived: ArchivedConversation): NoticeEntry {
  return {
    kind: 'notice',
    level: 'error',
    text: `${archived.reason}\nMoved it to ${archived.archive_name} and started a new conversation.`,
  }
}

/** Replace the room with `snapshot`. The input carries over; the files are read again. */
export function applySnapshot(state: RoomState, snapshot: RoomSnapshot): RoomState {
  const archived = snapshot.archived_conversation ?? null
  return {
    ...state,
    loaded: true,
    story: snapshot.story,
    modelName: snapshot.model_name,
    modelFromStory: snapshot.model_from_story,
    entries: archived ? [archiveNotice(archived), ...snapshot.entries] : [...snapshot.entries],
    hiddenEntries: snapshot.hidden_entries,
    agenda: [...snapshot.agenda],
    agendaError: snapshot.agenda_error ?? null,
    activity: snapshot.activity ?? 'idle',
    toolName: snapshot.tool_name ?? null,
    queue: [...(snapshot.queue ?? [])],
    archived,
    scriptRevision: state.scriptRevision + 1,
    loreRevision: state.loreRevision + 1,
  }
}

function withEntries(state: RoomState, entries: LogEntry[]): RoomState {
  return { ...state, entries }
}

function updateEntry(
  state: RoomState,
  matches: (entry: LogEntry) => boolean,
  update: (entry: LogEntry) => LogEntry
): RoomState {
  const index = state.entries.findIndex(matches)
  if (index === -1) return state
  const entries = state.entries.slice()
  entries[index] = update(entries[index]!)
  return withEntries(state, entries)
}

/** The call a result belongs to: the latest one still working under that id, else the latest under it. */
function pendingToolCall(entries: readonly LogEntry[], toolCallId: string): LogEntry | undefined {
  let latest: LogEntry | undefined
  for (let index = entries.length - 1; index >= 0; index--) {
    const entry = entries[index]!
    if (entry.kind !== 'tool_call' || entry.tool_call_id !== toolCallId) continue
    if (entry.outcome === 'working') return entry
    latest ??= entry
  }
  return latest
}

function isReply(entry: LogEntry, replyId: string): boolean {
  return entry.kind === 'message' && entry.reply_id === replyId
}

function addNotice(state: RoomState, level: NoticeLevel, text: string): RoomState {
  return withEntries(state, [...state.entries, { kind: 'notice', level, text }])
}

type Reducers = { [T in RoomEventType]: (state: RoomState, event: EventOf<T>) => RoomState }

/** What each kind of event does to the room. `parity.test.ts` fails when the protocol gains one without an entry here. */
export const EVENT_REDUCERS: Reducers = {
  user_message_added: (state, event) =>
    withEntries(state, [
      ...state.entries,
      { kind: 'message', role: 'user', text: event.text, reply_id: null },
    ]),

  reply_started: (state, event) =>
    withEntries(state, [
      ...state.entries,
      { kind: 'message', role: 'writer', text: '', reply_id: event.reply_id },
    ]),

  reply_delta: (state, event) => {
    if (!state.entries.some((entry) => isReply(entry, event.reply_id))) {
      return withEntries(state, [
        ...state.entries,
        { kind: 'message', role: 'writer', text: event.text, reply_id: event.reply_id },
      ])
    }
    return updateEntry(
      state,
      (entry) => isReply(entry, event.reply_id),
      (entry) => (entry.kind === 'message' ? { ...entry, text: entry.text + event.text } : entry)
    )
  },

  reply_finished: (state, event) =>
    updateEntry(
      state,
      (entry) => isReply(entry, event.reply_id),
      (entry) => (entry.kind === 'message' ? { ...entry, reply_id: null } : entry)
    ),

  tool_call_started: (state, event) =>
    withEntries(state, [
      ...state.entries,
      {
        kind: 'tool_call',
        tool_call_id: event.tool_call_id,
        tool_name: event.tool_name,
        arguments: event.arguments,
        result: null,
        outcome: 'working',
        sealed: event.sealed ?? false,
      },
    ]),

  tool_call_finished: (state, event) => {
    const call = pendingToolCall(state.entries, event.tool_call_id)
    return updateEntry(
      state,
      (entry) => entry === call,
      (entry) =>
        entry.kind === 'tool_call'
          ? { ...entry, result: event.result, outcome: event.outcome, sealed: Boolean(entry.sealed || event.sealed) }
          : entry
    )
  },

  activity_changed: (state, event) => ({
    ...state,
    activity: event.activity,
    toolName: event.activity === 'using_tool' ? (event.tool_name ?? null) : null,
  }),

  queue_changed: (state, event) => ({ ...state, queue: [...event.prompts] }),

  agenda_changed: (state, event) => ({ ...state, agenda: [...event.items], agendaError: null }),

  story_files_changed: (state, event) => ({
    ...state,
    scriptRevision: state.scriptRevision + (event.script ? 1 : 0),
    loreRevision: state.loreRevision + (event.lore ? 1 : 0),
  }),

  turn_finished: (state, event) => {
    // A turn that ends leaves no reply streaming, whatever the last event said.
    const entries = state.entries.map((entry) =>
      entry.kind === 'message' && entry.reply_id !== null ? { ...entry, reply_id: null } : entry
    )
    const next = entries.some((entry, index) => entry !== state.entries[index])
      ? withEntries(state, entries)
      : state
    if (event.outcome === 'interrupted') return addNotice(next, 'info', INTERRUPTED_NOTICE)
    if (event.outcome === 'failed') return addNotice(next, 'error', event.error || FAILED_NOTICE)
    return next
  },

  conversation_replaced: (state, event) => ({
    ...state,
    entries: [...event.entries],
    hiddenEntries: event.hidden_entries,
  }),

  draft_restored: (state, event) => ({
    ...state,
    draft: state.draft.trim() ? `${event.text}\n\n${state.draft}` : event.text,
  }),

  model_changed: (state, event) => ({ ...state, modelName: event.model_name, modelFromStory: true }),

  notice: (state, event) => addNotice(state, event.level, event.text),
}

export function applyEvent(state: RoomState, event: RoomEvent): RoomState {
  const reduce = EVENT_REDUCERS[event.type] as (state: RoomState, event: RoomEvent) => RoomState
  return reduce(state, event)
}

/** The activity line under the log: empty when it is the user's move. */
export function activityLabel(state: Pick<RoomState, 'activity' | 'toolName'>): string {
  switch (state.activity) {
    case 'thinking':
      return 'Thinking…'
    case 'writing':
      return 'Writing…'
    case 'using_tool':
      return state.toolName ? `Using ${state.toolName}…` : 'Using a tool…'
    default:
      return ''
  }
}

export function isWorking(state: Pick<RoomState, 'activity'>): boolean {
  return state.activity !== 'idle'
}
