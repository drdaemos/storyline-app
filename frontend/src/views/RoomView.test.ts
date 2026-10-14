import { flushPromises, mount } from '@vue/test-utils'
import * as client from '@/api/client'
import type { RoomStreamHandlers } from '@/api/sse'
import type { RoomEvent, RoomSnapshot } from '@/protocol/types'
import RoomView from './RoomView.vue'

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  openStory: vi.fn(),
  sendPrompt: vi.fn(),
  interrupt: vi.fn(),
  readScript: vi.fn(),
  listLore: vi.fn(),
  readLore: vi.fn(),
}))

const SNAPSHOT: RoomSnapshot = {
  story: 'tale',
  model_name: 'muse-1',
  model_from_story: false,
  entries: [
    { kind: 'message', role: 'user', text: 'Make Ines older.', reply_id: null },
    { kind: 'message', role: 'writer', text: 'I would **keep** the barometer.', reply_id: null },
    {
      kind: 'tool_call',
      tool_call_id: 't1',
      tool_name: 'read_lore',
      arguments: '{"filename":"ines.md"}',
      result: 'Fifty-eight.',
      outcome: 'success',
    },
  ],
  hidden_entries: 2,
  agenda: [{ id: 'a', title: 'The ferry scene', status: 'waiting', outcome: '' }],
  agenda_error: null,
  activity: 'idle',
  tool_name: null,
  queue: [],
  archived_conversation: null,
}

let handlers: RoomStreamHandlers

function mountRoom() {
  vi.mocked(client.openStory).mockImplementation((_story, given) => {
    handlers = given
    return { close: () => undefined }
  })
  vi.mocked(client.readScript).mockResolvedValue({ text: 'The ferry had stopped.' })
  vi.mocked(client.listLore).mockResolvedValue({ files: [] })
  vi.mocked(client.readLore).mockRejectedValue(new client.ApiError(404, 'No such file.'))
  return mount(RoomView, {
    props: { name: 'tale' },
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

async function emit(event: RoomEvent): Promise<void> {
  handlers.onEvent(event)
  await flushPromises()
}

describe('RoomView', () => {
  it('draws the room from the snapshot', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    expect(wrapper.text()).toContain('Make Ines older.')
    expect(wrapper.find('.note--writer strong').text()).toBe('keep')
    expect(wrapper.text()).toContain('2 earlier entries not shown')
    expect(wrapper.text()).toContain('The ferry scene')
    expect(wrapper.text()).toContain('muse-1')
    expect(wrapper.text()).toContain('The ferry had stopped.')
  })

  it('expands a tool call to its request and result', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    const stamp = wrapper.get('.stamp__button')
    expect(stamp.text()).toContain('read_lore')
    expect(stamp.text()).toContain('success')
    expect(stamp.attributes('aria-expanded')).toBe('false')
    await stamp.trigger('click')
    expect(stamp.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.stamp__details').text()).toContain('Fifty-eight.')
  })

  it('streams a reply, names what the writer is doing, and offers Stop', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    await emit({ type: 'activity_changed', activity: 'thinking', tool_name: null })
    expect(wrapper.get('[role="status"][aria-live="polite"]').text()).toBe('Thinking…')
    await emit({ type: 'reply_started', reply_id: 'r1' })
    await emit({ type: 'reply_delta', reply_id: 'r1', text: 'Which scene' })
    await emit({ type: 'reply_delta', reply_id: 'r1', text: ' next?' })
    expect(wrapper.findAll('.note--writer').at(-1)?.text()).toBe('Which scene next?')
    expect(wrapper.findAll('button').map((button) => button.text())).toContain('Stop')
    await emit({ type: 'activity_changed', activity: 'idle', tool_name: null })
    expect(wrapper.get('[role="status"][aria-live="polite"]').text()).toBe('')
    expect(wrapper.findAll('button').map((button) => button.text())).not.toContain('Stop')
  })

  it('puts a restored draft in the input', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    await emit({ type: 'draft_restored', text: 'Take it back' })
    expect(wrapper.get('textarea').element.value).toBe('Take it back')
  })

  it('sends the typed prompt to this story and empties the input', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    vi.mocked(client.sendPrompt).mockResolvedValue(undefined)
    await wrapper.get('textarea').setValue('  Keep the dog.  ')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(client.sendPrompt).toHaveBeenCalledWith('tale', 'Keep the dog.')
    expect(wrapper.get('textarea').element.value).toBe('')
  })

  it('gives the prompt back and says why when sending fails', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    vi.mocked(client.sendPrompt).mockRejectedValue(new client.ApiError(0, 'Could not reach the server.'))
    await wrapper.get('textarea').setValue('Keep the dog.')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.get('textarea').element.value).toBe('Keep the dog.')
    expect(wrapper.get('[role="alert"]').text()).toBe('Could not reach the server.')
  })

  it('replaces the log when the conversation is replaced', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    await emit({ type: 'conversation_replaced', entries: [], hidden_entries: 0 })
    expect(wrapper.text()).not.toContain('Make Ines older.')
  })

  it('shows the bookmarks as a tablist with Script open first', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.map((tab) => tab.text())).toEqual(['Script', 'Lore', 'Plan', 'Style', 'Agreement'])
    expect(tabs[0]?.attributes('aria-selected')).toBe('true')
    await tabs[2]!.trigger('click')
    await flushPromises()
    expect(tabs[2]?.attributes('aria-selected')).toBe('true')
    expect(wrapper.get('#panel-plan').text()).toContain('No plan has been written yet.')
  })

  it('moves between bookmarks with the arrow keys', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    const tabs = wrapper.findAll('[role="tab"]')
    await tabs[0]!.trigger('keydown', { key: 'ArrowRight' })
    expect(tabs[1]?.attributes('aria-selected')).toBe('true')
    await tabs[1]!.trigger('keydown', { key: 'End' })
    expect(tabs[4]?.attributes('aria-selected')).toBe('true')
    await tabs[4]!.trigger('keydown', { key: 'ArrowRight' })
    expect(tabs[0]?.attributes('aria-selected')).toBe('true')
  })

  it('marks the Book tab when the writer changes the files while the conversation is shown', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    const book = wrapper.get('[data-pane="book"]')
    expect(book.find('.room__tab-mark').exists()).toBe(false)
    await emit({ type: 'activity_changed', activity: 'using_tool', tool_name: 'write_script' })
    await emit({ type: 'story_files_changed', script: true, lore: false })
    expect(book.find('.room__tab-mark').exists()).toBe(true)
    expect(book.text()).toContain('updated')
    await book.trigger('click')
    expect(book.find('.room__tab-mark').exists()).toBe(false)
  })

  it('marks the Conversation tab when the writer finishes while the book is shown', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    await wrapper.get('[data-pane="book"]').trigger('click')
    const conversation = wrapper.get('[data-pane="conversation"]')
    await emit({ type: 'activity_changed', activity: 'thinking', tool_name: null })
    expect(conversation.find('.room__tab-mark').exists()).toBe(false)
    await emit({ type: 'activity_changed', activity: 'idle', tool_name: null })
    expect(conversation.find('.room__tab-mark').exists()).toBe(true)
    await conversation.trigger('click')
    expect(conversation.find('.room__tab-mark').exists()).toBe(false)
  })

  it('does not mark the Book tab for the snapshot a reconnect brings', async () => {
    const wrapper = mountRoom()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    handlers.onSnapshot(SNAPSHOT)
    await flushPromises()
    expect(wrapper.get('[data-pane="book"]').find('.room__tab-mark').exists()).toBe(false)
  })
})
