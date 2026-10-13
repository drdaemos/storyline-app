/**
 * Hand-written types for `protocol.json`, which is generated from the Python source of truth
 * (`src/storyline/room/protocol.py`). `parity.test.ts` keeps the two in step.
 */
import protocol from './protocol.json'

export type Operation =
  | 'list_stories'
  | 'create_story'
  | 'open_story'
  | 'send_prompt'
  | 'interrupt'
  | 'set_model'
  | 'undo_last_turn'
  | 'clear_conversation'
  | 'read_script'
  | 'list_lore'
  | 'read_lore'

export type Activity = 'idle' | 'thinking' | 'writing' | 'using_tool'

export type AgendaStatus = 'open' | 'working' | 'waiting' | 'settled' | 'dropped'

export interface AgendaItem {
  id: string
  title: string
  status: AgendaStatus
  outcome: string
}

export interface MessageEntry {
  kind: 'message'
  role: 'user' | 'writer'
  text: string
  /** Set while the writer is still streaming this reply; later deltas with the same id extend it. */
  reply_id: string | null
}

export interface ToolCallEntry {
  kind: 'tool_call'
  tool_call_id: string
  tool_name: string
  /** A JSON string. */
  arguments: string
  result: string | null
  /** `working` until the tool returns; then the tool's outcome, `retry` or `interrupted`. */
  outcome: string
}

export type Entry = MessageEntry | ToolCallEntry

export interface ArchivedConversation {
  reason: string
  archive_name: string
}

export interface RoomSnapshot {
  story: string
  model_name: string
  model_from_story: boolean
  entries: Entry[]
  hidden_entries: number
  agenda: AgendaItem[]
  agenda_error: string | null
  activity: Activity
  tool_name: string | null
  queue: string[]
  archived_conversation: ArchivedConversation | null
}

export type TurnOutcome = 'completed' | 'interrupted' | 'failed'

export type NoticeLevel = 'info' | 'error'

export type RoomEvent =
  | { type: 'user_message_added'; text: string }
  | { type: 'reply_started'; reply_id: string }
  | { type: 'reply_delta'; reply_id: string; text: string }
  | { type: 'reply_finished'; reply_id: string }
  | { type: 'tool_call_started'; tool_call_id: string; tool_name: string; arguments: string }
  | { type: 'tool_call_finished'; tool_call_id: string; result: string; outcome: string }
  | { type: 'activity_changed'; activity: Activity; tool_name: string | null }
  | { type: 'queue_changed'; prompts: string[] }
  | { type: 'agenda_changed'; items: AgendaItem[] }
  | { type: 'story_files_changed'; script: boolean; lore: boolean }
  | { type: 'turn_finished'; outcome: TurnOutcome; error: string | null }
  | { type: 'conversation_replaced'; entries: Entry[]; hidden_entries: number }
  | { type: 'draft_restored'; text: string }
  | { type: 'model_changed'; model_name: string }
  | { type: 'notice'; level: NoticeLevel; text: string }

export type RoomEventType = RoomEvent['type']

export type EventOf<T extends RoomEventType> = Extract<RoomEvent, { type: T }>

/** Bodies of the HTTP API, as the server sends them. */
export interface StoryList {
  stories: string[]
  active: string | null
}

export interface LoreFileSummary {
  filename: string
  summary: string | null
  keywords: string[] | string | null
}

const EVENT_TYPES: ReadonlySet<string> = new Set(protocol.events)

export function isRoomEvent(value: unknown): value is RoomEvent {
  if (typeof value !== 'object' || value === null) return false
  const type = (value as { type?: unknown }).type
  return typeof type === 'string' && EVENT_TYPES.has(type)
}
