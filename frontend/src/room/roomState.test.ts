import type { AgendaItem, Entry, RoomEvent, RoomSnapshot } from '@/protocol/types'
import {
  FAILED_NOTICE,
  INTERRUPTED_NOTICE,
  activityLabel,
  applyEvent,
  applySnapshot,
  initialRoomState,
  isWorking,
} from './roomState'
import type { RoomState } from './roomState'

function snapshot(overrides: Partial<RoomSnapshot> = {}): RoomSnapshot {
  return {
    story: 'tale',
    preset: 'default',
    model_name: 'muse-1',
    model_from_story: false,
    entries: [],
    hidden_entries: 0,
    agenda: [],
    agenda_error: null,
    activity: 'idle',
    tool_name: null,
    queue: [],
    archived_conversation: null,
    ...overrides,
  }
}

const userEntry: Entry = { kind: 'message', role: 'user', text: 'Hello', reply_id: null }
const toolEntry: Entry = {
  kind: 'tool_call',
  tool_call_id: 't1',
  tool_name: 'read_lore',
  arguments: '{}',
  result: null,
  outcome: 'working',
}

function loaded(overrides: Partial<RoomState> = {}): RoomState {
  return { ...applySnapshot(initialRoomState('tale'), snapshot()), ...overrides }
}

describe('applySnapshot', () => {
  it('replaces everything the room shows', () => {
    const agenda: AgendaItem[] = [{ id: 'a', title: 'The ferry', status: 'working', outcome: '' }]
    const state = applySnapshot(
      loaded({ entries: [userEntry], queue: ['old'], agenda: [] }),
      snapshot({
        model_name: 'muse-2',
        model_from_story: true,
        entries: [{ kind: 'message', role: 'writer', text: 'Hi', reply_id: 'r1' }],
        hidden_entries: 3,
        agenda,
        agenda_error: 'bad agenda',
        activity: 'using_tool',
        tool_name: 'write_script',
        queue: ['next'],
      })
    )
    expect(state).toMatchObject({
      loaded: true,
      story: 'tale',
      modelName: 'muse-2',
      modelFromStory: true,
      hiddenEntries: 3,
      agenda,
      agendaError: 'bad agenda',
      activity: 'using_tool',
      toolName: 'write_script',
      queue: ['next'],
    })
    expect(state.entries).toEqual([{ kind: 'message', role: 'writer', text: 'Hi', reply_id: 'r1' }])
  })

  it('marks the room loaded and asks for the files to be read again', () => {
    const before = initialRoomState('tale')
    const after = applySnapshot(before, snapshot())
    expect(before.loaded).toBe(false)
    expect(after.loaded).toBe(true)
    expect(after.scriptRevision).toBeGreaterThan(before.scriptRevision)
    expect(after.loreRevision).toBeGreaterThan(before.loreRevision)
  })

  it('keeps what the user has typed', () => {
    expect(applySnapshot(loaded({ draft: 'typing' }), snapshot()).draft).toBe('typing')
  })

  it('shows a conversation that could not be read as an error notice first', () => {
    const state = applySnapshot(
      initialRoomState('tale'),
      snapshot({
        entries: [userEntry],
        archived_conversation: { reason: 'The file was damaged.', archive_name: 'old-1.json' },
      })
    )
    expect(state.entries[0]).toMatchObject({ kind: 'notice', level: 'error' })
    expect(state.entries[0]).toMatchObject({ text: expect.stringContaining('old-1.json') })
    expect(state.entries[1]).toEqual(userEntry)
  })

  it('does not share arrays with the snapshot', () => {
    const source = snapshot({ entries: [userEntry], queue: ['a'] })
    const state = applySnapshot(initialRoomState('tale'), source)
    expect(state.entries).not.toBe(source.entries)
    expect(state.queue).not.toBe(source.queue)
  })
})

describe('event reducers', () => {
  const reduce = (state: RoomState, event: RoomEvent) => applyEvent(state, event)

  it('user_message_added appends a user message', () => {
    const state = reduce(loaded(), { type: 'user_message_added', text: 'Make it older' })
    expect(state.entries).toEqual([
      { kind: 'message', role: 'user', text: 'Make it older', reply_id: null },
    ])
  })

  it('reply_started appends a streaming writer reply', () => {
    const state = reduce(loaded(), { type: 'reply_started', reply_id: 'r1' })
    expect(state.entries).toEqual([{ kind: 'message', role: 'writer', text: '', reply_id: 'r1' }])
  })

  it('reply_delta extends the reply with that id and no other', () => {
    let state = loaded()
    state = reduce(state, { type: 'reply_started', reply_id: 'r1' })
    state = reduce(state, { type: 'user_message_added', text: 'between' })
    state = reduce(state, { type: 'reply_started', reply_id: 'r2' })
    state = reduce(state, { type: 'reply_delta', reply_id: 'r1', text: 'Hel' })
    state = reduce(state, { type: 'reply_delta', reply_id: 'r1', text: 'lo' })
    expect(state.entries.map((entry) => (entry.kind === 'message' ? entry.text : ''))).toEqual([
      'Hello',
      'between',
      '',
    ])
  })

  it('reply_delta starts a reply it has not heard of', () => {
    const state = reduce(loaded(), { type: 'reply_delta', reply_id: 'late', text: 'Hi' })
    expect(state.entries).toEqual([{ kind: 'message', role: 'writer', text: 'Hi', reply_id: 'late' }])
  })

  it('reply_finished ends the streaming mark and keeps the text', () => {
    let state = reduce(loaded(), { type: 'reply_started', reply_id: 'r1' })
    state = reduce(state, { type: 'reply_delta', reply_id: 'r1', text: 'Done' })
    state = reduce(state, { type: 'reply_finished', reply_id: 'r1' })
    expect(state.entries).toEqual([{ kind: 'message', role: 'writer', text: 'Done', reply_id: null }])
  })

  it('does not change the entries when a delta or finish names an unknown reply', () => {
    const before = loaded({ entries: [userEntry] })
    expect(reduce(before, { type: 'reply_finished', reply_id: 'nope' })).toBe(before)
  })

  it('tool_call_started appends a working tool call', () => {
    const state = reduce(loaded(), {
      type: 'tool_call_started',
      tool_call_id: 't1',
      tool_name: 'read_lore',
      arguments: '{"filename":"ines.md"}',
    })
    expect(state.entries).toEqual([
      {
        kind: 'tool_call',
        tool_call_id: 't1',
        tool_name: 'read_lore',
        arguments: '{"filename":"ines.md"}',
        result: null,
        outcome: 'working',
        sealed: false,
      },
    ])
  })

  it('keeps a call sealed from its start, and a finished event for it cannot unseal it', () => {
    let state = reduce(loaded(), {
      type: 'tool_call_started',
      tool_call_id: 's1',
      tool_name: 'read_lore',
      arguments: '{}',
      sealed: true,
    })
    expect(state.entries[0]).toMatchObject({ sealed: true })
    state = reduce(state, { type: 'tool_call_finished', tool_call_id: 's1', result: 'ok', outcome: 'success' })
    expect(state.entries[0]).toMatchObject({ sealed: true, result: 'ok' })
  })

  it('seals a call whose finished event says so', () => {
    const state = reduce(loaded({ entries: [toolEntry] }), {
      type: 'tool_call_finished',
      tool_call_id: 't1',
      result: 'ok',
      outcome: 'success',
      sealed: true,
    })
    expect(state.entries[0]).toMatchObject({ sealed: true })
  })

  it('tool_call_finished fills in the result and outcome of that call only', () => {
    const other: Entry = { ...toolEntry, tool_call_id: 't2' } as Entry
    const state = reduce(loaded({ entries: [toolEntry, other] }), {
      type: 'tool_call_finished',
      tool_call_id: 't1',
      result: 'ok',
      outcome: 'success',
    })
    expect(state.entries[0]).toMatchObject({ result: 'ok', outcome: 'success' })
    expect(state.entries[1]).toMatchObject({ result: null, outcome: 'working' })
  })

  it('tool_call_finished settles the call still working when an earlier turn used the same id', () => {
    const earlier: Entry = { ...toolEntry, result: 'old', outcome: 'success' } as Entry
    const state = reduce(loaded({ entries: [earlier, toolEntry] }), {
      type: 'tool_call_finished',
      tool_call_id: 't1',
      result: 'new',
      outcome: 'success',
    })
    expect(state.entries[0]).toMatchObject({ result: 'old', outcome: 'success' })
    expect(state.entries[1]).toMatchObject({ result: 'new', outcome: 'success' })
  })

  it('activity_changed sets the activity, and the tool only while a tool is used', () => {
    let state = reduce(loaded(), { type: 'activity_changed', activity: 'using_tool', tool_name: 'write_script' })
    expect(state).toMatchObject({ activity: 'using_tool', toolName: 'write_script' })
    state = reduce(state, { type: 'activity_changed', activity: 'writing', tool_name: 'write_script' })
    expect(state).toMatchObject({ activity: 'writing', toolName: null })
    state = reduce(state, { type: 'activity_changed', activity: 'idle', tool_name: null })
    expect(state.activity).toBe('idle')
  })

  it('queue_changed replaces the queue', () => {
    const state = reduce(loaded({ queue: ['old'] }), { type: 'queue_changed', prompts: ['a', 'b'] })
    expect(state.queue).toEqual(['a', 'b'])
  })

  it('agenda_changed replaces the agenda and clears an agenda error', () => {
    const items: AgendaItem[] = [{ id: 'a', title: 'The arc', status: 'waiting', outcome: '' }]
    const state = reduce(loaded({ agendaError: 'broken' }), { type: 'agenda_changed', items })
    expect(state.agenda).toEqual(items)
    expect(state.agendaError).toBeNull()
  })

  it('story_files_changed goes up for the files that changed only', () => {
    const before = loaded()
    const script = reduce(before, { type: 'story_files_changed', script: true, lore: false })
    expect(script.scriptRevision).toBe(before.scriptRevision + 1)
    expect(script.loreRevision).toBe(before.loreRevision)
    const lore = reduce(before, { type: 'story_files_changed', script: false, lore: true })
    expect(lore.scriptRevision).toBe(before.scriptRevision)
    expect(lore.loreRevision).toBe(before.loreRevision + 1)
    const both = reduce(before, { type: 'story_files_changed', script: true, lore: true })
    expect(both.scriptRevision).toBe(before.scriptRevision + 1)
    expect(both.loreRevision).toBe(before.loreRevision + 1)
  })

  describe('turn_finished', () => {
    it('adds nothing after a completed turn', () => {
      const before = loaded({ entries: [userEntry] })
      expect(reduce(before, { type: 'turn_finished', outcome: 'completed', error: null })).toBe(before)
    })

    it('says so when the turn was interrupted', () => {
      const state = reduce(loaded(), { type: 'turn_finished', outcome: 'interrupted', error: null })
      expect(state.entries).toEqual([{ kind: 'notice', level: 'info', text: INTERRUPTED_NOTICE }])
    })

    it('shows the error when the turn failed, or says that it did', () => {
      const withError = reduce(loaded(), { type: 'turn_finished', outcome: 'failed', error: 'Rate limited.' })
      expect(withError.entries).toEqual([{ kind: 'notice', level: 'error', text: 'Rate limited.' }])
      const without = reduce(loaded(), { type: 'turn_finished', outcome: 'failed', error: null })
      expect(without.entries).toEqual([{ kind: 'notice', level: 'error', text: FAILED_NOTICE }])
    })

    it('leaves no reply streaming', () => {
      const streaming = reduce(loaded(), { type: 'reply_started', reply_id: 'r1' })
      const state = reduce(streaming, { type: 'turn_finished', outcome: 'completed', error: null })
      expect(state.entries[0]).toMatchObject({ reply_id: null })
    })
  })

  it('conversation_replaced swaps the whole log', () => {
    const state = reduce(loaded({ entries: [userEntry, toolEntry], hiddenEntries: 9 }), {
      type: 'conversation_replaced',
      entries: [toolEntry],
      hidden_entries: 2,
    })
    expect(state.entries).toEqual([toolEntry])
    expect(state.hiddenEntries).toBe(2)
  })

  it('draft_restored fills an empty input', () => {
    expect(reduce(loaded(), { type: 'draft_restored', text: 'Undone prompt' }).draft).toBe('Undone prompt')
  })

  it('draft_restored goes ahead of what is already typed, with a blank line between', () => {
    const state = reduce(loaded({ draft: 'Already typing' }), { type: 'draft_restored', text: 'Undone prompt' })
    expect(state.draft).toBe('Undone prompt\n\nAlready typing')
  })

  it('draft_restored ignores typed text that is only whitespace', () => {
    expect(reduce(loaded({ draft: '  \n' }), { type: 'draft_restored', text: 'Back' }).draft).toBe('Back')
  })

  it('model_changed sets the model and marks it as the story\'s own', () => {
    const state = reduce(loaded(), { type: 'model_changed', model_name: 'muse-9' })
    expect(state).toMatchObject({ modelName: 'muse-9', modelFromStory: true })
  })

  it('notice adds a notice to the log', () => {
    const state = reduce(loaded(), { type: 'notice', level: 'error', text: 'Nope.' })
    expect(state.entries).toEqual([{ kind: 'notice', level: 'error', text: 'Nope.' }])
  })

  it('never changes the state it was given', () => {
    const before = loaded({ entries: [userEntry], queue: ['a'] })
    const frozen = JSON.stringify(before)
    reduce(before, { type: 'reply_started', reply_id: 'r' })
    reduce(before, { type: 'queue_changed', prompts: [] })
    reduce(before, { type: 'conversation_replaced', entries: [], hidden_entries: 0 })
    expect(JSON.stringify(before)).toBe(frozen)
  })
})

describe('activityLabel and isWorking', () => {
  it('is empty and not working when idle', () => {
    expect(activityLabel({ activity: 'idle', toolName: null })).toBe('')
    expect(isWorking({ activity: 'idle' })).toBe(false)
  })

  it('names what the writer does', () => {
    expect(activityLabel({ activity: 'thinking', toolName: null })).toBe('Thinking…')
    expect(activityLabel({ activity: 'writing', toolName: null })).toBe('Writing…')
    expect(activityLabel({ activity: 'using_tool', toolName: 'read_lore' })).toBe('Using read_lore…')
    expect(isWorking({ activity: 'thinking' })).toBe(true)
  })
})
