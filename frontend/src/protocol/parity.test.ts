import { OPERATION_CLIENT } from '@/api/client'
import { EVENT_REDUCERS } from '@/room/roomState'
import protocol from './protocol.json'
import type { EventOf, RoomEventType, RoomSnapshot } from './types'

/**
 * The web interface offers exactly the protocol's operations and renders exactly its events.
 * `protocol.json` is generated from the Python source of truth; when it changes, these fail until
 * the client, the reducers and `types.ts` catch up.
 */

type FieldsOf<T> = { [K in keyof T]-?: true }

// Compile-time completeness: adding a field to a type in `types.ts` fails here until it is listed.
const SNAPSHOT_FIELDS: FieldsOf<RoomSnapshot> = {
  story: true,
  preset: true,
  model_name: true,
  model_from_story: true,
  entries: true,
  hidden_entries: true,
  agenda: true,
  agenda_error: true,
  clocks: true,
  hidden_clocks: true,
  activity: true,
  tool_name: true,
  queue: true,
  archived_conversation: true,
}

const EVENT_FIELDS: { [T in RoomEventType]: FieldsOf<Omit<EventOf<T>, 'type'>> } = {
  user_message_added: { text: true },
  reply_started: { reply_id: true },
  reply_delta: { reply_id: true, text: true },
  reply_finished: { reply_id: true },
  tool_call_started: { tool_call_id: true, tool_name: true, arguments: true, sealed: true },
  tool_call_finished: { tool_call_id: true, result: true, outcome: true, sealed: true },
  activity_changed: { activity: true, tool_name: true },
  queue_changed: { prompts: true },
  agenda_changed: { items: true },
  clocks_changed: { clocks: true, hidden: true },
  story_files_changed: { script: true, lore: true },
  turn_finished: { outcome: true, error: true },
  conversation_replaced: { entries: true, hidden_entries: true },
  draft_restored: { text: true },
  model_changed: { model_name: true },
  notice: { level: true, text: true },
}

const sorted = (values: Iterable<string>): string[] => [...values].sort()

describe('protocol parity', () => {
  it('has a reducer for every event, and no reducer for an event the protocol lacks', () => {
    expect(sorted(Object.keys(EVENT_REDUCERS))).toEqual(sorted(protocol.events))
  })

  it('has a client function for every operation, and none for an operation the protocol lacks', () => {
    expect(sorted(Object.keys(OPERATION_CLIENT))).toEqual(sorted(protocol.operations))
    for (const operation of protocol.operations) {
      expect(typeof OPERATION_CLIENT[operation as keyof typeof OPERATION_CLIENT]).toBe('function')
    }
  })

  it('agrees with the event schema about which events exist', () => {
    expect(sorted(Object.keys(protocol.event_schema.discriminator.mapping))).toEqual(sorted(protocol.events))
  })

  it('types every event with exactly the fields of its schema', () => {
    const definitions = protocol.event_schema.$defs as unknown as Record<string, { properties: Record<string, unknown> }>
    const mapping = protocol.event_schema.discriminator.mapping as Record<string, string>
    for (const type of protocol.events) {
      const definition = definitions[mapping[type]!.replace('#/$defs/', '')]
      const schemaFields = Object.keys(definition!.properties).filter((field) => field !== 'type')
      expect(sorted(Object.keys(EVENT_FIELDS[type as RoomEventType])), type).toEqual(sorted(schemaFields))
    }
  })

  it('types the snapshot with exactly the fields of its schema', () => {
    expect(sorted(Object.keys(SNAPSHOT_FIELDS))).toEqual(sorted(Object.keys(protocol.snapshot_schema.properties)))
  })
})
